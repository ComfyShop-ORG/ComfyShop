from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from comfyshop_api.main import create_app
from comfyshop_api.models import Workflow


def test_web_routes_serve_index_and_keep_asset_and_api_errors(settings, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    (dist / "assets" / "bundle.js").write_text("export {};", encoding="utf-8")
    settings.static_dir = dist

    with TestClient(create_app(settings)) as client:
        for path in ("/", "/workspace", "/workspace/tasks", "/machines", "/workflows/example"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/html")
            assert response.text == '<div id="root"></div>'

        assert client.head("/workspace/tasks").status_code == 200
        assert client.post("/workspace/tasks").status_code == 405
        assert client.get("/assets/bundle.js").text == "export {};"
        for path in ("/assets/missing", "/missing.svg", "/api", "/api/v1/missing"):
            assert client.get(path).status_code == 404
        assert client.get("/api/v1/health").json()["status"] == "ok"


def test_public_workflow_links_carry_a_share_preview(settings, tmp_path, graph):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<head><title>ComfyShop</title></head>", encoding="utf-8")
    settings.static_dir = dist

    with TestClient(create_app(settings), headers={"Origin": "http://testserver"}) as client:
        session = client.post(
            "/api/v1/auth/register", json={"username": "author", "password": "correct-horse"}
        ).json()
        client.headers["X-CSRF-Token"] = session["csrfToken"]
        workflow = client.post(
            "/api/v1/workflows", json={"name": '<人像> "工作流"', "graph": graph}
        ).json()
        path = f"/workflows/{workflow['id']}"
        # 私有工作流的页面不带名称，访客看不到它的存在。
        assert client.get(path).text == "<head><title>ComfyShop</title></head>"
        with Session(client.app.state.engine) as db:
            record = db.get(Workflow, workflow["id"])
            record.published = True
            record.description = "自然光人像"
            db.commit()
        page = client.get(path).text
        assert "<title>&lt;人像&gt; &quot;工作流&quot; · ComfyShop</title>" in page
        assert '<meta property="og:description" content="自然光人像" />' in page


def test_worker_package_download_carries_the_platform_address(settings, tmp_path):
    from io import BytesIO
    import json
    from zipfile import ZipFile

    dist = tmp_path / "dist"
    (dist / "downloads").mkdir(parents=True)
    with ZipFile(dist / "downloads" / "comfyshop-worker.zip", "w") as bundle:
        bundle.writestr("comfyshop-worker-1.0/start.sh", "#!/bin/sh")
    settings.static_dir = dist

    def server_url() -> str:
        with TestClient(create_app(settings)) as client:
            response = client.get("/api/v1/worker/package")
            assert response.status_code == 200
            with ZipFile(BytesIO(response.content)) as bundle:
                assert "comfyshop-worker-1.0/start.sh" in bundle.namelist()
                config = json.loads(bundle.read("comfyshop-worker-1.0/worker.json"))
        assert config["comfyUrl"] == "http://127.0.0.1:8188"
        return config["serverUrl"]

    # 反向代理后请求地址可能是内网或 http，配置的平台地址优先。
    settings.public_url = "https://comfyshop.example"
    assert server_url() == "https://comfyshop.example"
    settings.public_url = None
    assert server_url() == "http://testserver"
