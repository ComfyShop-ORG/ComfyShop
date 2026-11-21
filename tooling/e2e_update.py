"""Publish isolated signed releases and verify updates through the work machine UI."""

import json
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from e2e_scenario import login, request, wait_for
from playwright.sync_api import expect

from comfyshop_worker.release import Build, version_number

TOOLING = Path(__file__).resolve().parent
REJECTED = "发布包签名或版本校验失败"


class TestReleases:
    def __init__(self, scratch):
        self.key_path = scratch / "signing.pem"
        key = Ed25519PrivateKey.generate()
        self.key_path.write_bytes(
            key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
        )
        self.public_key = key.public_key().public_bytes_raw().hex()
        project = TOOLING.parent / "integrations/comfyui/pyproject.toml"
        version = tomllib.loads(project.read_text(encoding="utf-8"))["project"]["version"]
        major, minor, patch = version_number(version)
        self.packages = {}
        for lane, options in (
            ("baseline", []),
            ("invalid", ["--test-version", f"{major}.{minor}.{patch + 1}"]),
            ("valid", ["--test-version", f"{major}.{minor}.{patch + 2}"]),
        ):
            package = scratch / f"{lane}.zip"
            subprocess.run(
                [sys.executable, "-B", TOOLING / "build-worker.py", "--output", package, *options],
                capture_output=True,
                check=True,
                timeout=120,
            )
            self.packages[lane] = package

    def publish(self, directory, lane):
        # The container may read the signed public files under a different UID.
        subprocess.run(
            [
                sys.executable,
                "-B",
                TOOLING / "publish-worker-release.py",
                "--package",
                self.packages[lane],
                "--key",
                self.key_path,
                directory,
            ],
            capture_output=True,
            check=True,
            timeout=30,
            umask=0o022,
        )
        manifest = directory / "release.json"
        record = json.loads(manifest.read_bytes())
        release = record["release"]
        if lane == "invalid":
            # Corrupt only the signature. The served archive still has the advertised SHA-256.
            old = release["signature"]
            release["signature"] = ("0" if old[0] != "0" else "1") + old[1:]
            temporary = directory / "release.new"
            temporary.write_text(json.dumps(record), encoding="utf-8")
            temporary.chmod(0o644)
            temporary.replace(manifest)
        return release


def verify_update(browser, client, credentials, machine, release, folder, *, valid):
    address = str(client.base_url).rstrip("/")
    machine_path = f"/machines/{machine['id']}"
    name = machine["name"]
    expected_status = "succeeded" if valid else "failed"
    expected_build = Build.from_record(release if valid else machine["runtime"])
    context = browser.new_context(
        base_url=address,
        viewport={"width": 390, "height": 844} if valid else {"width": 1280, "height": 900},
        has_touch=valid,
    )
    try:
        page = context.new_page()
        login(page, address, credentials)
        page.goto("/machines")
        page.get_by_role("button", name=f"{name} 操作", exact=True).click()
        with page.expect_response(
            lambda reply: (
                urlsplit(reply.url).path == f"/api/v1{machine_path}/update"
                and reply.request.method == "PUT"
            )
        ) as response:
            page.get_by_role("menuitem", name="更新到最新版", exact=True).click()
        assert response.value.ok and response.value.json()["update"]["status"] == "pending"

        def updated():
            current = next(
                row
                for row in request(client, "GET", "/machines").json()["items"]
                if row["id"] == machine["id"]
            )
            if (current["update"] or {}).get("status") in ("failed", "succeeded"):
                return current
            return None

        current = wait_for(updated, timeout=420)
        update = current["update"]
        assert update["status"] == expected_status, update
        assert current["online"] and current["id"] == machine["id"]
        assert Build.from_record(current["runtime"]) == expected_build
        assert update["release"]["sha256"] == release["sha256"]
        assert current["updateAvailable"] is not valid
        page.reload()
        entry = page.locator(".machine-item").filter(has=page.get_by_text(name, exact=True))
        expect(entry.get_by_text("在线", exact=True)).to_be_visible()
        expect(entry.locator(f'[title="{expected_build.build}"]')).to_contain_text(
            f"版本 {expected_build.version}"
        )
        if not valid:
            assert update["error"] == REJECTED
            expect(entry.get_by_role("status")).to_have_text(REJECTED)
        page.screenshot(path=folder / f"update-{expected_status}.png", animations="disabled")
        return {
            "status": update["status"],
            "machine": current["id"],
            "version": expected_build.version,
            "build": expected_build.build,
            "releaseSha256": release["sha256"],
            "error": update["error"],
        }
    finally:
        context.close()
