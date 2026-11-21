"""Verify real work machines against isolated Team and SQLite deployments."""

import argparse
import json
import os
import re
import secrets
import signal
import socket
import subprocess
import sys
from contextlib import ExitStack, contextmanager, suppress
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import IPv4Address
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.parse import urlsplit

import httpx
from e2e_native import inventory
from e2e_scenario import (
    approve,
    client_for,
    create_workflow,
    real_result,
    register,
    replay,
    share,
    submit_publisher,
    wait_for,
)
from e2e_update import TestReleases, verify_update
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
NATIVE = Path(__file__).with_name("e2e_native.py")
PLATFORMS = {
    "linux-x64": ("Linux", {"x86_64"}),
    "linux-arm64": ("Linux", {"aarch64", "arm64"}),
    "macos-arm64": ("Darwin", {"arm64"}),
    "macos-x64": ("Darwin", {"x86_64"}),
    "windows-x64": ("Windows", {"AMD64", "x86_64"}),
}


def docker(args, *command, **kwargs):
    prefix = ["docker", "--context", args.docker_context] if args.docker_context else ["docker"]
    return subprocess.run([*prefix, *command], cwd=REPO, text=True, **kwargs)


def free_port(bind):
    with socket.socket() as listener:
        listener.bind((bind, 0))
        return listener.getsockname()[1]


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)


@contextmanager
def record_cleanup(evidence, session, *, preserve_failure):
    try:
        yield
    except Exception as error:
        evidence["cleanupError"] = str(error).replace(session.key, "[session]")
        if not preserve_failure:
            raise


def compose_project(args, folder, edition, image, project, address, port, release_dir):
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("COMFYSHOP_", "COMPOSE_"))
    }
    profile = []
    source = "compose.yaml"
    if edition == "team":
        source = "compose.team.yaml"
        profile = ["--profile", "rustfs"]
        env.update(
            COMFYSHOP_POSTGRES_PASSWORD=secrets.token_hex(20),
            COMFYSHOP_STORAGE_BACKEND="s3",
            COMFYSHOP_S3_ENDPOINT_URL="http://rustfs:9000",
            COMFYSHOP_S3_BUCKET=project,
            COMFYSHOP_S3_ADDRESSING_STYLE="path",
            COMFYSHOP_S3_ACCESS_KEY_ID="e2e" + secrets.token_hex(8),
            COMFYSHOP_S3_SECRET_ACCESS_KEY=secrets.token_hex(24),
        )
    resolved = docker(
        args,
        "compose",
        "--env-file",
        os.devnull,
        "-f",
        source,
        "-p",
        project,
        *profile,
        "config",
        "--format",
        "json",
        env=env,
        check=True,
        capture_output=True,
    )
    spec = json.loads(resolved.stdout)
    for name, volume in spec["volumes"].items():
        volume.pop("external", None)
        volume["name"] = f"{project}_{name}"
    for name, network in spec["networks"].items():
        network.pop("external", None)
        network["name"] = f"{project}_{name}"
    for name, service in spec["services"].items():
        if service.get("network_mode") or any(
            mount["type"] != "volume" or mount["source"] not in spec["volumes"]
            for mount in service.get("volumes", ())
        ):
            raise ValueError(f"{name} uses storage or networking outside the test project")
        service.pop("restart", None)
        if name in {"app", "rustfs-init"}:
            service.pop("build", None)
            service["image"] = image
    app = spec["services"]["app"]
    app["environment"]["COMFYSHOP_PUBLIC_URL"] = address
    if release_dir:
        app["volumes"].append(
            {
                "type": "bind",
                "source": str(release_dir),
                "target": "/data/worker-releases",
                "read_only": True,
                "bind": {"create_host_path": False},
            }
        )
    app["ports"] = [
        {"target": 8688, "published": str(port), "host_ip": args.bind, "protocol": "tcp"}
    ]
    if "rustfs-init" in spec["services"]:
        spec["services"]["rustfs-init"]["tmpfs"] = ["/data"]
    config = folder / "compose.json"
    write_json(config, spec)
    return (
        ["compose", "--env-file", os.devnull, "-f", str(config), "-p", project, *profile],
        [volume["name"] for volume in spec["volumes"].values()],
    )


class NativeSession:
    def __init__(self, bind, client_ip, manual):
        self.key = "/" + secrets.token_urlsafe(25)
        self.command = {}
        self.host = None
        self.report = None
        self.native_source = NATIVE.read_bytes()
        session = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def send_content(self, data, mime_type):
                self.send_response(200)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def respond(self, content):
                self.send_content(json.dumps(content).encode(), "application/json")

            def allowed(self, path):
                return self.path == session.key + path and (
                    not client_ip or self.client_address[0] == client_ip
                )

            def do_GET(self):
                if self.allowed(""):
                    self.respond(session.command)
                elif manual and self.allowed("/native.py"):
                    self.send_content(session.native_source, "application/octet-stream")
                else:
                    self.send_error(404)

            def do_POST(self):
                if not (self.allowed("/host") or self.allowed("/report")):
                    self.send_error(404)
                    return
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 256 * 1024:
                    self.send_error(400)
                    return
                value = json.loads(self.rfile.read(size))
                if self.allowed("/host") and session.host is None:
                    session.host = value
                elif self.allowed("/report") and value.get("seq") == session.command.get("seq"):
                    session.report = value
                else:
                    self.send_error(409)
                    return
                self.respond({"received": True})

        self.server = ThreadingHTTPServer((bind, 0), Handler)
        self.ticket = f"http://{bind}:{self.server.server_port}{self.key}"
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def issue(self, action, **values):
        self.report = None
        self.command = {"seq": self.command.get("seq", 0) + 1, "action": action, **values}
        report = wait_for(lambda: self.report, timeout=400 if action == "start" else 25)
        if "error" in report:
            raise RuntimeError(report["error"])
        return {key: value for key, value in report.items() if key != "seq"}

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def launch_native(args, session, folder):
    if args.executor == "manual":
        write_json(
            folder / "native-ticket.json",
            {
                "ticket": session.ticket,
                "root": args.native_root,
                "nativeSha256": sha256(session.native_source).hexdigest(),
            },
        )
        print(
            f"Waiting for the native test host. Private ticket: {folder / 'native-ticket.json'}",
            flush=True,
        )
        return None
    root = args.native_root or str(folder / "native")
    if args.executor == "local":
        command = [sys.executable, "-B", str(NATIVE), session.ticket, root]
        code = None
    else:
        executable = "python.exe" if args.target.startswith("windows-") else "python3"
        command = [
            "ssh",
            *(["-F", args.ssh_config] if args.ssh_config else []),
            "-b",
            args.bind,
            "-T",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "ConnectTimeout=10",
            args.ssh_host,
            executable,
            "-B",
            "-",
        ]
        argv = [NATIVE.name, session.ticket, root]
        code = (
            f"import sys\nsys.argv = {ascii(argv)}\n" + NATIVE.read_text(encoding="utf-8")
        ).encode()
    with (folder / "native.log").open("wb") as output:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE if code else subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
    if code:
        assert process.stdin is not None
        with process.stdin as stream:
            stream.write(code)
    return process


def stop_containers(args, compose, folder, edition, evidence):
    targets = [("app", "/data")]
    if edition == "team":
        targets += [("db", "/var/lib/postgresql/data"), ("rustfs", "/data")]
    sizes = {}
    try:
        for service, mount in targets:
            measurement = docker(
                args,
                *compose,
                "exec",
                "-T",
                service,
                "du",
                "-sk",
                mount,
                capture_output=True,
                timeout=20,
            )
            if measurement.returncode == 0:
                sizes[service] = int(measurement.stdout.split()[0]) * 1024
    finally:
        evidence["volumeBytes"] = sizes
        try:
            with (folder / "compose-service.log").open("w", encoding="utf-8") as log:
                docker(
                    args,
                    *compose,
                    "logs",
                    "--no-color",
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=20,
                )
        finally:
            result = docker(
                args, *compose, "down", "--timeout", "10", capture_output=True, timeout=75
            )
            evidence["containersStopped"] = result.returncode == 0
            result.check_returncode()


def test_edition(args, edition, browser, comfy, session, image, run, evidence, releases):
    folder = run / edition
    folder.mkdir(mode=0o700)
    prefix = f"ComfyShop-e2e/{run.name}/{edition}/result"
    port = free_port(args.bind)
    site = f"http://{args.bind}:{port}"
    project = f"e2e-{run.name}-{edition}"
    release_dir = folder / "worker-releases" if releases else None
    if releases:
        assert release_dir
        release_dir.mkdir(mode=0o755)
        release_dir.chmod(0o755)
        baseline = releases.publish(release_dir, "baseline")
        evidence["updates"] = {
            "baseline": {key: baseline[key] for key in ("version", "build", "sha256")}
        }
    compose, volumes = compose_project(
        args, folder, edition, image, project, site, port, release_dir
    )
    evidence.update(
        project=project,
        volumes=volumes,
        site=site,
        comfyOutputPrefix=prefix,
        downloads={},
        tasks={},
        status="failed",
    )
    try:
        with (folder / "compose-start.log").open("w", encoding="utf-8") as log:
            docker(
                args,
                *compose,
                "up",
                "-d",
                "--no-build",
                "--wait",
                "--wait-timeout",
                "180",
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=360,
            )
        with client_for(site) as publisher, client_for(site) as reader:
            digest = sha256(
                publisher.get("/api/v1/worker/package").raise_for_status().content
            ).hexdigest()
            machines = {}
            accounts = {
                "publisher": (publisher, register(publisher)),
                "reader": (reader, register(reader)),
            }
            for role, (client, credentials) in accounts.items():
                print(f"{args.target}/{edition}: starting {role} from the served ZIP", flush=True)
                record = session.issue(
                    "start",
                    runId=run.name,
                    edition=edition,
                    role=role,
                    site=site,
                    comfy=args.comfy,
                    sha256=digest,
                    publicKey=releases.public_key if releases else None,
                )
                code = record.pop("pairingCode")
                evidence["downloads"][role] = record
                machine = approve(browser, client, credentials, code, role, folder)
                if "build" in record:
                    assert machine["runtime"]["version"] == record["version"]
                    assert machine["runtime"]["build"] == record["build"]
                if releases:
                    assert machine["runtime"]["canUpdate"]
                    assert machine["runtime"]["build"] == baseline["build"]
                record["nodes"] = machine["nodeCount"]
                machines[role] = machine
            assert machines["publisher"]["id"] != machines["reader"]["id"]
            workflow = create_workflow(publisher, prefix)
            task, asset = submit_publisher(publisher, workflow, machines["publisher"])
            evidence["tasks"]["publisher"] = {"task": task["id"]}
            result = real_result(publisher, comfy, task["id"], folder, "publisher")
            evidence["tasks"]["publisher"] = result
            work, shared = share(publisher, reader, workflow, asset, result)
            evidence["sharedAssetSha256"] = shared["sha256"]
            for width in ("desktop", "mobile"):
                if releases:
                    valid = width == "mobile"
                    lane = "valid" if valid else "invalid"
                    release = releases.publish(release_dir, lane)
                    print(
                        f"{args.target}/{edition}: verifying the {lane} signed update", flush=True
                    )
                    update = verify_update(
                        browser,
                        reader,
                        accounts["reader"][1],
                        machines["reader"],
                        release,
                        folder,
                        valid=valid,
                    )
                    evidence["updates"][lane] = update

                    def installed(digest=release["sha256"] if valid else None):
                        record = session.issue(
                            "installed-update", runId=run.name, edition=edition, role="reader"
                        )
                        return record if (record["current"] or {}).get("sha256") == digest else None

                    marker = wait_for(installed, timeout=20)
                    if valid:
                        assert marker["current"]["publicKey"] == releases.public_key
                        assert marker["build"] == {
                            "version": release["version"],
                            "build": release["build"],
                        }
                    update["installed"] = marker["current"] is not None

                task_id = replay(
                    browser,
                    reader,
                    accounts["reader"][1],
                    workflow,
                    work,
                    machines["reader"],
                    shared,
                    width,
                    folder,
                )
                evidence["tasks"][width] = {"task": task_id}
                evidence["tasks"][width] = real_result(reader, comfy, task_id, folder, width)
                if releases:
                    evidence["updates"][lane]["verifiedWithTask"] = task_id
            assert len({item["promptId"] for item in evidence["tasks"].values()}) == 3
        evidence["status"] = "passed"
        print(f"{args.target}/{edition}: passed (publisher and two browser replays)", flush=True)
    finally:
        with record_cleanup(evidence, session, preserve_failure=sys.exception() is not None):
            try:
                evidence["nativeStop"] = session.issue("stop")
            finally:
                stop_containers(args, compose, folder, edition, evidence)


def main(args):
    os.umask(0o077)
    bind = IPv4Address(args.bind)
    if bind.is_unspecified or bind.is_multicast:
        raise ValueError("Bind the test deployment to a specific IPv4 interface")
    root = args.root.resolve()
    if root.is_relative_to(REPO):
        raise ValueError("Choose a storage root outside the checkout")
    suffix = args.run_id or secrets.token_hex(5)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,22}", suffix):
        raise ValueError("Use a run ID of up to 23 lowercase letters, digits and hyphens")
    address = urlsplit(args.comfy)
    if (
        address.scheme not in {"http", "https"}
        or not address.hostname
        or address.username
        or address.path not in ("", "/")
    ):
        raise ValueError("Pass the test ComfyUI origin")
    run = root / f"{suffix}-{args.target}"
    run.mkdir(parents=True, mode=0o700)
    args.comfy = args.comfy.rstrip("/")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    image = args.image or f"comfyshop:e2e-{run.name}"
    evidence = {
        "revision": revision,
        "target": args.target,
        "root": str(run),
        "image": image,
        "editions": {},
        "status": "failed",
    }
    print(f"Regression storage: {run}", flush=True)
    try:
        with ExitStack() as stack:
            comfy = stack.enter_context(
                httpx.Client(base_url=args.comfy, timeout=20, trust_env=False)
            )
            data = comfy.get("/system_stats").raise_for_status().json()
            info = data["system"]
            arguments = info.get("argv", [])
            evidence["comfy"] = {
                "origin": args.comfy,
                "os": info.get("os"),
                "version": info.get("comfyui_version"),
                "devices": [item["name"] for item in data["devices"]],
                "inputOutputDirectories": {
                    key: arguments[arguments.index(key) + 1]
                    for key in ("--input-directory", "--output-directory")
                    if key in arguments
                },
            }
            session = NativeSession(args.bind, args.native_ip, args.executor == "manual")
            stack.callback(session.close)
            native = launch_native(args, session, run)
            try:

                def attached():
                    if native is not None and native.poll() is not None:
                        raise RuntimeError(f"Native test host exited; see {run / 'native.log'}")
                    return session.host

                host = wait_for(attached, timeout=420 if args.executor == "manual" else 50)
                evidence["nativeHost"] = host
                system, architectures = PLATFORMS[args.target]
                assert host["os"] == system and host["arch"] in architectures, host
                if not args.image:
                    with (run / "image-build.log").open("w", encoding="utf-8") as log:
                        docker(
                            args,
                            "build",
                            "--label",
                            f"org.opencontainers.image.revision={revision}",
                            "--tag",
                            image,
                            ".",
                            check=True,
                            stdout=log,
                            stderr=subprocess.STDOUT,
                            timeout=1500,
                        )
                (image_data,) = json.loads(
                    docker(args, "image", "inspect", image, capture_output=True, check=True).stdout
                )
                evidence["imageId"] = image_data["Id"]
                evidence["imageBytes"] = image_data["Size"]
                evidence["imageRevision"] = (image_data["Config"].get("Labels") or {}).get(
                    "org.opencontainers.image.revision"
                )
                releases = None
                if args.updates:
                    if evidence["imageRevision"] != revision:
                        raise ValueError(
                            "The update regression needs an app image built from this revision"
                        )
                    scratch = Path(stack.enter_context(TemporaryDirectory(dir=run)))
                    releases = TestReleases(scratch)
                pw = stack.enter_context(sync_playwright())
                browser = pw.chromium.launch()
                stack.callback(browser.close)
                for edition in args.edition or ("team", "sqlite"):
                    row = evidence["editions"][edition] = {}
                    try:
                        test_edition(
                            args, edition, browser, comfy, session, image, run, row, releases
                        )
                    except Exception as error:
                        row.update(
                            status="failed", error=str(error).replace(session.key, "[session]")
                        )
                        print(f"{args.target}/{edition}: {row['error']}", flush=True)
                if any(row["status"] != "passed" for row in evidence["editions"].values()):
                    raise RuntimeError(f"A worker regression failed; see {run / 'report.json'}")
            finally:
                with record_cleanup(
                    evidence, session, preserve_failure=sys.exception() is not None
                ):
                    try:
                        if session.host:
                            evidence["nativeFinish"] = session.issue("finish")
                    finally:
                        if native is not None:
                            if native.poll() is None:
                                try:
                                    native.wait(timeout=15)
                                except subprocess.TimeoutExpired:
                                    native.terminate()
                                    native.wait(timeout=10)
                            if native.returncode:
                                raise RuntimeError(
                                    f"Native test host exited with {native.returncode}; see {run / 'native.log'}"
                                )
        evidence["status"] = "passed"
    except KeyboardInterrupt:
        evidence.update(status="cancelled", error="Regression interrupted")
        raise
    except Exception as error:
        evidence["error"] = str(error).replace(
            getattr(locals().get("session"), "key", "\0"), "[session]"
        )
        raise
    finally:
        with suppress(OSError):
            evidence["controllerStorage"] = inventory(run)
        write_json(run / "report.json", evidence)


def interrupt(_signum, _frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupt)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--target", choices=PLATFORMS, required=True)
    parser.add_argument("--comfy", required=True)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--run-id")
    parser.add_argument("--docker-context")
    parser.add_argument("--image", help="Use a prebuilt app image instead of building the checkout")
    parser.add_argument("--edition", action="append", choices=["team", "sqlite"])
    parser.add_argument(
        "--updates", action="store_true", help="Exercise rejected and successful signed updates"
    )
    parser.add_argument("--executor", choices=["local", "ssh", "manual"], default="local")
    parser.add_argument("--ssh-host")
    parser.add_argument("--ssh-config")
    parser.add_argument("--native-root")
    parser.add_argument("--native-ip", help="Restrict the controller to this source address")
    options = parser.parse_args()
    if options.executor == "ssh" and (
        not options.ssh_host or not re.fullmatch(r"[a-zA-Z0-9_.-]+", options.ssh_host)
    ):
        parser.error("--executor ssh requires a valid SSH alias")
    if options.executor != "local" and (options.bind == "127.0.0.1" or not options.native_root):
        parser.error("Remote execution needs --bind and --native-root")
    main(options)
