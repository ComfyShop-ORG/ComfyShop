"""Portable widget metadata; exclude connections, private credentials and file lists."""

import math


def make_catalog(info: dict) -> dict:
    nodes = {}
    for name, node in info.items():
        inputs = {}
        schema = node.get("input", {})
        for field, definition in {
            **schema.get("required", {}),
            **schema.get("optional", {}),
        }.items():
            if not definition or not isinstance(definition, list):
                continue
            if any(
                part in field.lower()
                for part in [
                    "api_key",
                    "apikey",
                    "access_token",
                    "password",
                    "secret",
                    "authorization",
                ]
            ):
                continue
            kind = definition[0]
            options = (
                definition[1] if len(definition) > 1 and isinstance(definition[1], dict) else {}
            )
            choices = []
            if options.get("video_upload") or (
                name in {"LoadVideo", "VHS_LoadVideo", "VHS_LoadVideoPath"}
                and field in {"file", "video", "video_path"}
            ):
                kind = "video"
            elif options.get("image_upload") or (
                name in {"LoadImage", "LoadImageMask"} and field == "image"
            ):
                kind = "image"
            elif isinstance(kind, list):
                choices, kind = kind, "choice"
            elif kind == "COMBO":
                choices, kind = options.get("options", []), "choice"
            else:
                kind = (
                    {
                        "STRING": "string",
                        "INT": "integer",
                        "FLOAT": "number",
                        "BOOLEAN": "boolean",
                    }.get(kind)
                    if isinstance(kind, str)
                    else None
                )
            if not kind or options.get("forceInput"):
                continue
            choices = [
                v
                for v in choices
                if isinstance(v, (str, bool, int, float))
                and (not isinstance(v, float) or math.isfinite(v))
            ]
            if kind == "choice" and (not choices or len(choices) > 5000):
                continue
            inputs[field] = {
                "kind": kind,
                "label": str(options.get("display_name", ""))[:160],
                "choices": choices,
                "minimum": str(options["min"]) if "min" in options else None,
                "maximum": str(options["max"]) if "max" in options else None,
                "step": str(options["step"]) if "step" in options else None,
                "multiline": bool(options.get("multiline")),
            }
        nodes[name] = {
            "title": str(node.get("display_name", name))[:160],
            "outputNode": bool(node.get("output_node")),
            "inputs": inputs,
        }
    return {"nodes": nodes}
