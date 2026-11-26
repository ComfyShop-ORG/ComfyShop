import gzip

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
        for path in (
            "/",
            "/?q=portrait",
            "/skill",
            "/workflows/example",
            "/workspace/assets",
            "/workspace/tasks",
            "/machines",
            "/machines/link?code=ABCDEFGH",
            "/reset-password",
        ):
            response = client.get(path, follow_redirects=False)
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/html")
            assert response.headers["content-language"] == "zh-CN"
            assert response.text == '<div id="root"></div>'

        assert client.head("/workspace/tasks").status_code == 200
        assert client.post("/workspace/tasks").status_code == 405
        assert client.get("/assets/bundle.js").text == "export {};"
        for path in ("/index.html", "/assets/missing", "/missing.svg", "/api", "/api/v1/missing"):
            assert client.get(path).status_code == 404
        assert client.get("/api/v1/health").json()["status"] == "ok"


def test_static_scripts_negotiate_compression_and_revalidate_each_variant(settings, tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (tmp_path / "index.html").write_text("<title>ComfyShop</title>")
    script = b"export default " + repr("model preview" * 64).encode()
    compressed = gzip.compress(script)
    (assets / "preview.js").write_bytes(script)
    (assets / "preview.js.gz").write_bytes(compressed)
    settings.static_dir = tmp_path
    path = "/assets/preview.js"
    with TestClient(create_app(settings)) as client:
        encoded = client.get(path, headers={"Accept-Encoding": "br, GZip; q=0.9"})
        assert encoded.content == script and encoded.headers["content-encoding"] == "gzip"
        assert "javascript" in encoded.headers["content-type"]
        assert int(encoded.headers["content-length"]) == len(compressed)
        assert encoded.headers["vary"] == "Accept-Encoding"

        for accept in ("", "br", "gzip;q=0, *;q=1", "gzip;q=0.2, identity;q=0.8"):
            identity = client.get(path, headers={"Accept-Encoding": accept})
            assert identity.content == script and "content-encoding" not in identity.headers
            assert int(identity.headers["content-length"]) == len(script)
            assert identity.headers["vary"] == "Accept-Encoding"
            assert identity.headers["etag"] != encoded.headers["etag"]

        headers = {"Accept-Encoding": "*", "If-None-Match": encoded.headers["etag"]}
        cached = client.get(path, headers=headers)
        assert cached.status_code == 304 and cached.headers["vary"] == "Accept-Encoding"
        assert (
            client.get(path, headers={**headers, "Accept-Encoding": "identity"}).status_code == 200
        )
        head = client.head(path, headers={"Accept-Encoding": "gzip"})
        assert head.content == b"" and int(head.headers["content-length"]) == len(compressed)
        assert head.headers["content-encoding"] == "gzip"
        partial = client.get(path, headers={"Accept-Encoding": "identity", "Range": "bytes=0-5"})
        assert partial.status_code == 206 and partial.content == script[:6]
        ranges = client.get(path, headers={"Accept-Encoding": "gzip", "Range": "bytes=0-2,8-10"})
        assert ranges.status_code == 200 and ranges.content == script
        assert client.get(path, headers={"Accept-Encoding": "*;q=0"}).status_code == 406


def test_web_and_api_negotiate_same_language(settings, tmp_path):
    (tmp_path / "index.html").write_text('<html lang="zh-CN"></html>')
    settings.static_dir = tmp_path
    settings.default_language = "ko"
    settings.menu_languages = "en,zh,zh,unknown"
    with TestClient(create_app(settings), follow_redirects=False) as client:
        for languages, language in (
            ("fr-FR, ja-JP;q=0.9, en;q=0.2", "ja"),
            ("en;q=0.2, ko;q=0.6, zh-Hant-HK;q=0.9", "zh-tw"),
            ("zh-Hans-TW", "zh"),
            ("zh-MO", "zh-tw"),
            ("en-GB;q=0.8, ja;q=0.8", "en"),
            ("ja;q=0, fr, *;q=0.5", "ko"),
            ("", "ko"),
        ):
            headers = {"Accept-Language": languages}
            root = client.get("/?q=cat", headers=headers)
            assert root.status_code == 200
            assert f'data-language="{language}"' in root.text
            assert root.headers["vary"] == "Cookie, Accept-Language"
            assert "comfyshop.language" not in root.cookies
            config = client.get("/api/v1/presentation", headers=headers).json()
            assert config == {"language": language, "menu": ["en", "zh"]}
        client.cookies.set("comfyshop.language", "unregistered")
        assert (
            client.get("/skill", headers={"Accept-Language": "ja"}).headers["content-language"]
            == "ja-JP"
        )
        client.cookies.set("comfyshop.language", "en")
        assert (
            client.get("/machines", headers={"Accept-Language": "ko"}).headers["content-language"]
            == "en"
        )
        assert (
            client.get("/api/v1/missing", headers={"Accept-Language": "ja"}).json()["detail"]
            == "API endpoint not found"
        )
        link = client.post("/api/v1/worker/links", json={"name": "Pairing test"}).raise_for_status()
        assert link.json()["verificationPath"] == "/machines/link"


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
            record.versions[0].published = True
            record.published_version_id = record.versions[0].id
            record.description = "自然光人像"
            db.commit()
        page = client.get(path).text
        assert "<title>&lt;人像&gt; &quot;工作流&quot; · ComfyShop</title>" in page
        assert '<meta property="og:description" content="自然光人像" />' in page
        english = client.get(path, headers={"Accept-Language": "en"})
        assert english.status_code == 200
        assert "og:title" in english.text and "自然光人像" in english.text
        assert english.headers["content-language"] == "en"


def test_worker_package_download_carries_the_platform_address(settings, tmp_path):
    import json
    from io import BytesIO
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
