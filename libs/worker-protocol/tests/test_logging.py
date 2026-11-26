import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("kind", ["comfyui", "official", "runninghub"])
def test_worker_log_level_format_and_context(kind: str) -> None:
    program = """
import sys
from comfyshop_worker_protocol.logging import logger, worker_logging
with worker_logging(sys.argv[1]):
    logger.debug("filtered message")
    with logger.contextualize(task_id="sample"):
        logger.warning("connection interrupted", http_status=503)
"""
    result = subprocess.run(
        [sys.executable, "-c", program, kind],
        capture_output=True,
        text=True,
        check=True,
        env=os.environ | {"COMFYSHOP_WORKER_LOG_LEVEL": "warning"},
    )
    [record] = result.stderr.splitlines()
    assert result.stdout == ""
    assert " | WARNING  | connection interrupted | " in record
    assert f"'worker_kind': '{kind}'" in record and "'task_id': 'sample'" in record
    assert "'http_status': 503" in record


def test_plugin_preserves_host_logs_and_background_log_rotates(tmp_path: Path) -> None:
    program = """
import sys
from pathlib import Path
from comfyshop_worker_protocol.logging import logger, worker_logging
with worker_logging("comfyui", embedded=True):
    logger.info("plugin connected")
logger.info("host ready")
with worker_logging("comfyui", file=Path(sys.argv[1])):
    for _ in range(4):
        logger.info("x" * (1024 * 1024))
    logger.info("service ready")
"""
    log = tmp_path / "worker.log"
    result = subprocess.run(
        [sys.executable, "-c", program, str(log)],
        capture_output=True,
        text=True,
        check=True,
        env=os.environ | {"COMFYSHOP_WORKER_LOG_LEVEL": "info"},
    )
    assert result.stderr.count("plugin connected") == result.stderr.count("host ready") == 1
    assert "'worker_kind': 'comfyui'" in result.stderr
    assert "service ready" in log.read_text(encoding="utf-8")
    assert len(list(tmp_path.glob("worker.*.log"))) == 2
