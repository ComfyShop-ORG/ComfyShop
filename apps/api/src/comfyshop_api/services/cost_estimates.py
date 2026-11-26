"""Prepare an authorized quote with the same inputs used for generation."""

import json
from contextlib import ExitStack, closing
from threading import BoundedSemaphore

import httpx
from fastapi import HTTPException
from pydantic import SecretStr, ValidationError
from sqlalchemy.orm import Session

from comfyshop_api.core.config import Settings
from comfyshop_api.core.i18n import msg
from comfyshop_api.models import Asset, TeamRole, WorkAsset, WorkflowVersion
from comfyshop_api.schemas import CostEstimate, GenerationInputs
from comfyshop_api.services.inputs import compile_inputs
from comfyshop_api.services.media_records import asset_read
from comfyshop_api.services.tasks import generation_source
from comfyshop_api.services.teams import TeamAccess
from comfyshop_api.services.worker_types import OFFICIAL
from comfyshop_api.services.works import selected_work_assets
from comfyshop_media.errors import MediaError
from comfyshop_media.storage import MediaStorage

_slots = BoundedSemaphore(4)


def can_estimate_cost(version: WorkflowVersion, config: Settings) -> bool:
    return (
        version.worker_kind == OFFICIAL.kind
        and version.format == "service"
        and bool(config.official_quote_url and config.worker_service_tokens.get(OFFICIAL.kind))
    )


def estimate_cost(
    db: Session,
    body: GenerationInputs,
    user_id: str,
    team: TeamAccess | None,
    config: Settings,
    language: str,
) -> CostEstimate:
    if team and not team.role.permits(TeamRole.EDITOR):
        raise HTTPException(403, msg("team.permissionDenied"))
    team_id = team.team.id if team else None
    _, version, source = generation_source(db, body, user_id, team_id)
    url = config.official_quote_url
    token = config.worker_service_tokens.get(OFFICIAL.kind)
    if not url or not token or not can_estimate_cost(version, config):
        raise HTTPException(404, msg("quote.unsupported"))

    shared = selected_work_assets(db, source, body.input_values) if source else {}
    graph, values, _, bindings = compile_inputs(
        db,
        version,
        None,
        body.input_values,
        body.input_schema_hash,
        owner_id=user_id,
        team_id=team_id,
        language=language,
        work_assets=shared,
    )
    assets: dict[str, Asset | WorkAsset] = {}
    inputs = []
    for binding in bindings:
        asset = shared.get(binding.input_name) or db.get(Asset, binding.asset_id)
        if asset is None:
            raise HTTPException(404, msg("asset.notFound"))
        assets[asset.id] = asset
        inputs.append(
            asset_read(asset).model_dump(by_alias=True) | {"inputName": binding.input_name}
        )
    originals = {asset_id: asset.media.storage_name for asset_id, asset in assets.items()}
    manifest = {"execution": graph, "inputValues": values, "assets": inputs}
    db.rollback()

    if not _slots.acquire(blocking=False):
        raise HTTPException(503, msg("quote.unavailable"))
    try:
        return _request_quote(url, token, config.media_storage, manifest, originals)
    finally:
        _slots.release()


def _request_quote(
    url: str,
    token: SecretStr,
    storage: MediaStorage,
    manifest: dict,
    originals: dict[str, str],
) -> CostEstimate:
    try:
        with ExitStack() as streams:
            files: list[tuple[str, tuple]] = [
                ("quote", (None, json.dumps(manifest, ensure_ascii=False)))
            ]
            for asset_id, name in originals.items():
                path = storage.original_path(name)
                source = streams.enter_context(
                    path.open("rb")
                    if path is not None
                    else closing(storage.open_original(name).body)
                )
                files.append((asset_id, (asset_id, source, "application/octet-stream")))
            response = httpx.post(
                url,
                files=files,
                headers={"Authorization": f"Bearer {token.get_secret_value()}"},
                timeout=httpx.Timeout(30, connect=3),
                trust_env=False,
            )
        if response.status_code == 404:
            raise HTTPException(404, msg("quote.unsupported"))
        return CostEstimate.model_validate_json(response.raise_for_status().content)
    except (httpx.HTTPError, ValidationError, OSError, MediaError):
        raise HTTPException(503, msg("quote.unavailable")) from None
