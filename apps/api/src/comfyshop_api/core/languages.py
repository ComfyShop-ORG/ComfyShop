"""展示语言注册表与 HTTP 语言协商。"""

import json
import re
from pathlib import Path

_manifest = json.loads(Path(__file__).with_name("languages.json").read_text(encoding="utf-8"))
LANGUAGES: dict[str, dict[str, str]] = _manifest["languages"]
DEFAULT_LANGUAGE: str = _manifest["default"]
LANGUAGE_COOKIE = "comfyshop.language"
_language_codes = {
    **{code: code for code in LANGUAGES},
    **{info["locale"].lower(): code for code, info in LANGUAGES.items()},
    **_manifest["languageAliases"],
}
_language_range = re.compile(
    r"([a-z]{1,8}(?:-[a-z0-9]{1,8})*)(?:\s*;\s*q\s*=\s*(0(?:\.\d{0,3})?|1(?:\.0{0,3})?))?",
    re.IGNORECASE | re.ASCII,
)


def preferred_language(accept_language: str, default: str) -> str:
    """按浏览器权重和排列顺序匹配语言，先匹配具体地区或文字，再回退到主语言。"""
    selected, best_weight = default, 0.0
    for entry in accept_language.split(","):
        match = _language_range.fullmatch(entry.strip())
        if not match:
            continue
        language, weight = match[1].lower(), float(match[2] or 1)
        if weight <= best_weight:
            continue
        while language:
            if code := _language_codes.get(language):
                selected, best_weight = code, weight
                break
            language = language.rpartition("-")[0]
    return selected


def language_menu(configured: str | None) -> list[str]:
    if configured is None:
        return list(LANGUAGES)
    return list(
        dict.fromkeys(code for part in configured.split(",") if (code := part.strip()) in LANGUAGES)
    )
