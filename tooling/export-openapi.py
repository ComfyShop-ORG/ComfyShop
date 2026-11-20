import json
from pathlib import Path

from comfyshop_api.main import create_app

root = Path(__file__).resolve().parent.parent
(root / "packages/api-client/openapi.json").write_text(
    json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n"
)
