"""Internal cost queries using the active work machine's provider account."""

import asyncio
import hashlib
import hmac
from collections.abc import Awaitable, Callable, Mapping
from typing import BinaryIO, TypedDict

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.datastructures import UploadFile

from .atlas_cloud import Atlas, AtlasSpec, RunError
from .atlas_media import MediaEncoding, atlas_media_reference, bind_atlas_media


class QuoteRequest(BaseModel):
    execution: dict
    input_values: dict = Field(alias="inputValues")
    assets: list[dict]


class UnitQuote(TypedDict):
    unitPrice: str
    currency: str
    estimated: bool


type QuoteAdapter = Callable[[QuoteRequest, dict[str, UploadFile]], Awaitable[UnitQuote]]


def _verify_source(source: BinaryIO, sha256: str) -> None:
    digest = hashlib.sha256()
    while chunk := source.read(1024 * 1024):
        digest.update(chunk)
    if digest.hexdigest() != sha256:
        raise ValueError("素材校验失败")
    source.seek(0)


async def quote_atlas(
    atlas: Atlas, request: QuoteRequest, files: dict[str, UploadFile]
) -> UnitQuote:
    spec = AtlasSpec.model_validate(request.execution["config"])
    payload = spec.payload(request.input_values)
    verified: set[str] = set()

    async def reference(
        asset: dict,
        *,
        encoding: MediaEncoding,
        alpha_requirement: str | None = None,
        reject_png_alpha: bool = False,
    ) -> str:
        asset_id = asset["id"]
        file = files[asset_id]
        if asset_id not in verified:
            if file.size != asset["size"]:
                raise ValueError("素材大小不一致")
            await asyncio.to_thread(_verify_source, file.file, asset["sha256"])
            verified.add(asset_id)
        else:
            await file.seek(0)
        return await atlas_media_reference(
            atlas,
            asset,
            file.file,
            encoding=encoding,
            alpha_requirement=alpha_requirement,
            reject_png_alpha=reject_png_alpha,
        )

    await bind_atlas_media(spec, payload, request.input_values, request.assets, reference)
    spec.validate_request_size(payload)
    price, estimated = await atlas.calculate(payload)
    return {"unitPrice": str(price), "currency": "USD", "estimated": estimated}


def quote_app(adapters: Mapping[str, QuoteAdapter], token: str) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    router = APIRouter()
    slots = asyncio.Semaphore(4)
    expected = f"Bearer {token}".encode()

    def authenticate(request: Request) -> None:
        if not hmac.compare_digest(request.headers.get("Authorization", "").encode(), expected):
            raise HTTPException(401)

    @router.post("/quote", dependencies=[Depends(authenticate)])
    async def quote(request: Request) -> UnitQuote:
        if slots.locked():
            raise HTTPException(503)
        try:
            async with (
                slots,
                asyncio.timeout(27),
                request.form(max_files=2000, max_fields=1, max_part_size=16 * 1024**2) as form,
            ):
                text = form.get("quote")
                if not isinstance(text, str):
                    raise ValueError("缺少报价参数")
                job = QuoteRequest.model_validate_json(text)
                adapter = job.execution.get("adapter")
                if not isinstance(adapter, str) or adapter not in adapters:
                    raise HTTPException(404)
                files = {name: file for name, file in form.items() if isinstance(file, UploadFile)}
                if files.keys() != {asset["id"] for asset in job.assets}:
                    raise ValueError("报价素材不匹配")
                return await adapters[adapter](job, files)
        except (httpx.HTTPError, RunError, KeyError, ValueError, OSError, TimeoutError):
            raise HTTPException(503) from None

    app.include_router(router)
    return app
