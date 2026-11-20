"""没有密钥时在浏览器确认接入，并把取得的密钥写入配置文件。"""

import asyncio
from io import StringIO
from collections.abc import Callable
import json
import os
from pathlib import Path
import socket
import sys
import time
from urllib.parse import urlsplit
import webbrowser

import httpx

from .config import Config, MissingKey


class LinkError(Exception):
    """接入没有完成，消息可直接显示给用户。"""


def can_open_browser() -> bool:
    """这台机器是否有可以直接打开网页的桌面环境。远程登录和无显示的 Linux 没有。"""
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"):
        return False
    if sys.platform in {"win32", "darwin"}:
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


LOOPBACK = {"localhost", "127.0.0.1", "::1"}


def qr_lines(url: str) -> list[str]:
    """把地址画成终端里可扫的二维码，每行一个字符串。缺少二维码库时返回空列表。"""
    try:
        import segno
    except ImportError:
        return []
    output = StringIO()
    segno.make(url, error="m").terminal(out=output, compact=True, border=2)
    return output.getvalue().splitlines()


def save_key(config_file: Path, api_key: str) -> None:
    """把密钥写进配置文件，保留其中的地址等设置。文件只对当前用户可读写。"""
    values = json.loads(config_file.read_text()) if config_file.exists() else {}
    if not isinstance(values, dict):
        raise LinkError("工作机配置必须是 JSON 对象")
    values["apiKey"] = api_key
    temporary = config_file.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as output:
        os.chmod(temporary, 0o600)
        json.dump(values, output, ensure_ascii=False, indent=2)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(config_file)


async def link_machine(
    server_url: str,
    config_file: Path,
    *,
    echo: Callable[[str], None] = print,
    open_browser: Callable[[str], bool] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    """向平台申请接入，等账号在网页确认后把密钥写入 `config_file`。

    有桌面环境时直接打开确认页，否则显示网址和代码，供另一台设备的浏览器使用。
    平台无法连接、申请过期或被拒绝时抛出 `LinkError`。
    """
    if open_browser is None:
        open_browser = webbrowser.open if can_open_browser() else None
    async with httpx.AsyncClient(
        base_url=server_url + "/api/v1/worker/",
        timeout=httpx.Timeout(30, connect=10),
        transport=transport,
    ) as client:
        try:
            response = await client.post("links", json={"name": socket.gethostname()[:80]})
        except httpx.TransportError:
            raise LinkError(
                f"无法连接平台 {server_url}。请确认 worker.json 里的 serverUrl。"
            ) from None
        if not response.is_success:
            raise LinkError(f"平台没有接受接入申请（{response.status_code}）。请稍后重试。")
        start = response.json()
        code = start["code"]
        url = f"{server_url}/machines/link?code={code}"
        opened = False
        if open_browser:
            try:
                opened = bool(open_browser(url))
            except Exception:
                opened = False
        if opened:
            echo("已在浏览器打开接入页面。登录后确认，这台工作机就会接入你的账号。")
            echo(f"浏览器没有打开时，手动访问：{url}")
        else:
            echo("用手机扫码，或在任意设备的浏览器打开下面的地址，登录后确认接入：")
            if urlsplit(server_url).hostname in LOOPBACK:
                echo("（平台地址是本机地址，其他设备打不开。请把地址开头换成平台的实际地址。）")
            else:
                for line in qr_lines(url):
                    echo(line)
            echo(f"  {url}")
            echo(f"或打开 {server_url}/machines/link 输入代码 {code[:4]}-{code[4:]}")
        echo("重装后可以在接入页选择重新连接原工作机。")
        echo("也可以在网页的工作机页面手动添加，把下载的 worker.json 放到启动文件旁后重新启动。")
        echo("等待确认…")
        deadline = time.monotonic() + start["expiresIn"]
        while time.monotonic() < deadline:
            await asyncio.sleep(start["interval"])
            try:
                response = await client.post("links/token", json={"secret": start["secret"]})
            except httpx.TransportError:
                continue
            if response.status_code == 410:
                break
            try:
                result = (
                    response.json() if response.is_success or response.status_code == 409 else None
                )
            except ValueError:
                # 例如反向代理临时返回的网页，下一轮再问。
                continue
            if not isinstance(result, dict):
                continue
            if response.status_code == 409:
                detail = result.get("detail")
                if isinstance(detail, str):
                    raise LinkError(f"{detail}。请重新启动工作机申请接入。")
                continue
            if result.get("status") == "approved":
                try:
                    save_key(config_file, result["apiKey"])
                except OSError as error:
                    raise LinkError(
                        f"无法把密钥写入 {config_file}：{error}。请检查文件权限后重新接入。"
                    ) from None
                echo(f"已接入：{result['machineName']}")
                return
    raise LinkError("接入申请已过期。重新启动工作机可以再次申请。")


def load_config(echo: Callable[[str], None] = print) -> Config:
    """读取配置。配置文件里没有密钥时先完成接入，再读取写入密钥后的配置。

    没有可写入密钥的配置文件时抛出原来的 `MissingKey`。
    """
    try:
        return Config.load()
    except MissingKey as missing:
        file = os.environ.get("COMFYSHOP_WORKER_CONFIG")
        if not file:
            raise
        asyncio.run(link_machine(missing.server_url, Path(file), echo=echo))
        return Config.load()
