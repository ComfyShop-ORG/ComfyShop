"""ComfyShop node metadata and leased HTTP transport."""

from typing import Literal

WorkerProtocolVersion = Literal[5]
PROTOCOL_VERSION: WorkerProtocolVersion = 5
DEFAULT_MAX_ARTIFACT_BYTES = 1024**3

LEASE_HEADER = "X-Task-Lease"
RECOVERY_HEADER = "X-Task-Recovery"
ERROR_CODE_HEADER = "X-ComfyShop-Error-Code"
TASK_CANCELLED = "task_cancelled"

TaskStage = Literal[
    "preflight",
    "connecting",
    "reconnecting",
    "waiting_for_comfy",
    "executing",
    "uploading",
    "cloud_waiting",
    "cloud_queued",
    "cloud_running",
]
