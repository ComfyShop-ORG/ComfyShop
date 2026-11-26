"""Render platform messages at the response boundary using stable keys."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request

from comfyshop_api.core.languages import LANGUAGE_COOKIE, LANGUAGES, preferred_language

_directory = Path(__file__).with_name("locales")
SOURCE_LANGUAGE = "zh"
_catalogs: dict[str, dict[str, str]] = {
    code: json.loads((_directory / f"{code}.json").read_text(encoding="utf-8"))
    for code in LANGUAGES
}
_source_keys = {text: key for key, text in _catalogs[SOURCE_LANGUAGE].items()}
# Official workers report these messages with the argument values already inserted.
_official_error_patterns = (
    (
        re.compile(r"Atlas Cloud 拒绝了生成请求（HTTP ([0-9]{3})）"),
        "officialWorker.requestRejected",
    ),
    (
        re.compile(r"读取 Atlas Cloud 生成结果失败（HTTP ([0-9]{3})）"),
        "officialWorker.resultReadFailed",
    ),
    (re.compile(r"Atlas Cloud 成品下载失败（HTTP ([0-9]{3})）"), "officialWorker.downloadFailed"),
    (re.compile(r"(.*) 至少需要 ([0-9]+) 份素材", re.DOTALL), "officialWorker.minAssets"),
    (re.compile(r"素材和生成数量合计最多 ([0-9]+)"), "officialWorker.combinedLimit"),
)


@dataclass(frozen=True, slots=True)
class Message:
    key: str
    values: tuple[object, ...]

    def __str__(self) -> str:
        return localize(self, SOURCE_LANGUAGE)


def msg(key: str, *values: object) -> Message:
    return Message(key, values)


def message_from_text(text: str) -> str | Message:
    """Resolve stored labels and dependency errors that only carry display text."""
    key = _source_keys.get(text)
    return msg(key) if key else text


def localize(text: str | Message, language: str) -> str:
    if isinstance(text, str):
        text = message_from_text(text)
        if isinstance(text, str):
            return text
    template = _catalogs[language][text.key]
    values = tuple(
        localize(value, language) if isinstance(value, Message) else value for value in text.values
    )
    return template.format(*values) if values else template


def localize_task_error(text: str | None, language: str, *, official: bool) -> str | None:
    if not text:
        return None
    if official and language != SOURCE_LANGUAGE:
        for pattern, key in _official_error_patterns:
            if match := pattern.fullmatch(text):
                return localize(msg(key, *match.groups()), language)
    return localize(text, language)


def request_language(request: Request) -> str:
    saved = request.cookies.get(LANGUAGE_COOKIE)
    if saved and saved in LANGUAGES:
        return saved
    return preferred_language(
        ",".join(request.headers.getlist("accept-language")), request.app.state.default_language
    )


Language = Annotated[str, Depends(request_language)]
