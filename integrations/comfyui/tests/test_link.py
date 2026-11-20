import asyncio
import json

import httpx
import pytest

from comfyshop_worker.config import Config, MissingKey
from comfyshop_worker.link import LinkError, link_machine


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    path = tmp_path / "worker.json"
    monkeypatch.setenv("COMFYSHOP_WORKER_CONFIG", str(path))
    monkeypatch.setenv("COMFYSHOP_WORKER_STATE_DIR", str(tmp_path / "state"))
    for variable in ("COMFYSHOP_SERVER_URL", "COMFYSHOP_COMFY_URL", "COMFYSHOP_API_KEY"):
        monkeypatch.delenv(variable, raising=False)
    return path


def platform(replies):
    """按顺序回放换取密钥的响应，记录收到的请求。"""
    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append((request.url.path, json.loads(request.content)))
        if request.url.path.endswith("/links"):
            return httpx.Response(
                201, json={"secret": "s3cret", "code": "ABCDEFGH", "expiresIn": 60, "interval": 0}
            )
        return replies.pop(0)

    return httpx.MockTransport(handle), requests


def test_first_start_links_the_machine_and_keeps_the_configured_addresses(config_file):
    config_file.write_text(
        json.dumps({"serverUrl": "http://platform.test", "comfyUrl": "http://c"})
    )
    with pytest.raises(MissingKey) as missing:
        Config.load()
    transport, requests = platform(
        [
            httpx.Response(200, json={"status": "pending"}),
            httpx.Response(
                200, json={"status": "approved", "apiKey": "cs_key", "machineName": "工作室"}
            ),
        ]
    )
    shown, opened = [], []
    asyncio.run(
        link_machine(
            missing.value.server_url,
            config_file,
            echo=shown.append,
            open_browser=lambda url: opened.append(url) or True,
            transport=transport,
        )
    )
    assert opened == ["http://platform.test/machines/link?code=ABCDEFGH"]
    assert requests[-1] == ("/api/v1/worker/links/token", {"secret": "s3cret"})
    assert json.loads(config_file.read_text()) == {
        "serverUrl": "http://platform.test",
        "comfyUrl": "http://c",
        "apiKey": "cs_key",
    }
    assert config_file.stat().st_mode & 0o777 == 0o600
    assert Config.load().api_key == "cs_key"
    assert any("工作室" in line for line in shown)


def test_without_a_desktop_the_address_and_code_are_shown_and_expiry_is_reported(config_file):
    transport, _ = platform([httpx.Response(410, json={"detail": "expired"})])
    shown = []
    with pytest.raises(LinkError):
        asyncio.run(
            link_machine(
                "http://platform.test",
                config_file,
                echo=shown.append,
                open_browser=lambda url: False,
                transport=transport,
            )
        )
    text = "\n".join(shown)
    assert "http://platform.test/machines/link?code=ABCDEFGH" in text and "ABCD-EFGH" in text
    # 地址同时画成二维码，手机扫码即可打开确认页。
    assert sum("█" in line for line in shown) > 10
    assert not config_file.exists()


def test_loopback_platform_address_is_not_offered_as_a_qr_code(config_file):
    transport, _ = platform([httpx.Response(410, json={"detail": "expired"})])
    shown = []
    with pytest.raises(LinkError):
        asyncio.run(
            link_machine(
                "http://127.0.0.1:8688",
                config_file,
                echo=shown.append,
                open_browser=lambda url: False,
                transport=transport,
            )
        )
    assert not any("█" in line for line in shown)
    assert any("实际地址" in line for line in shown)


def test_a_proxy_page_while_waiting_does_not_end_the_link(config_file):
    config_file.write_text(json.dumps({"serverUrl": "http://platform.test"}))
    transport, _ = platform(
        [
            httpx.Response(200, text="<html>gateway</html>"),
            httpx.Response(
                200, json={"status": "approved", "apiKey": "cs_key", "machineName": "工作室"}
            ),
        ]
    )
    asyncio.run(
        link_machine(
            "http://platform.test",
            config_file,
            echo=lambda _line: None,
            open_browser=lambda _url: True,
            transport=transport,
        )
    )
    assert json.loads(config_file.read_text())["apiKey"] == "cs_key"


def test_reconnection_conflict_is_shown_in_the_worker_window(config_file):
    detail = "请先停止原工作机，等它离线且空闲后重新连接"
    transport, _ = platform([httpx.Response(409, json={"detail": detail})])
    with pytest.raises(LinkError, match=detail):
        asyncio.run(
            link_machine(
                "http://platform.test",
                config_file,
                echo=lambda _line: None,
                open_browser=lambda _url: True,
                transport=transport,
            )
        )
    assert not config_file.exists()
