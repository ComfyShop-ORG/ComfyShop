"""Static references for framework consumers; never imported by application code."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from urllib.request import HTTPRedirectHandler
    from uvicorn import Server
    from zipfile import ZipInfo

    from comfyshop_api import schemas
    from comfyshop_worker.config import RunRecord, WorkerState
    from comfyshop_api.api.health import HealthResponse
    from comfyshop_api.core.categories import WorkflowCategory
    from comfyshop_api.core.config import Settings

    # Pydantic reads model configuration and serializes these fields dynamically.
    WorkflowCategory.VIDEO
    WorkflowCategory.AUDIO
    WorkflowCategory.MODEL_3D
    WorkflowCategory.VECTOR
    WorkflowCategory.LLM
    Settings.model_config
    HealthResponse.service
    schemas.AuthorRead.avatar_url
    schemas.MediaRead.src
    schemas.MediaRead.video_preview
    schemas.WorkflowRead.author
    schemas.WorkflowRead.author_profile
    schemas.WorkflowVersions.current_version_id
    schemas.WorkspaceRead.favorite_ids
    schemas.TaskActivity.active_tasks
    schemas.TaskActivity.completed_executions
    schemas.MachineRead.online
    schemas.MachineRead.busy
    schemas.MachineRead.revoked
    schemas.MachineRead.node_count
    schemas.MachineRead.update_available
    schemas.MachinePage.worker_release
    schemas.MachineHeartbeat.protocol_version
    schemas.ExecutionRead.image_count
    schemas.ExecutionRead.video_count
    schemas.ExecutionRead.audio_count
    schemas.ExecutionRead.model_count
    schemas.ExecutionRead.artifact_count
    schemas.WorkRead.asset_count
    schemas.WorkRead.author_profile
    schemas.NodeInput.multiline
    schemas.WorkflowInput.primary
    schemas.WorkflowInput.named
    schemas.MachineLinkStart.expires_in
    schemas.MachineLinkStart.interval
    schemas.MachineLinkRead.requested_at
    schemas.MachineLinkRead.same_network
    schemas.WorkflowParameterDisplay.display_name
    schemas.WorkflowParameterDisplay.help
    schemas.WorkflowRatioSize.ratio_field_id
    schemas.WorkflowRatioSize.megapixels_field_id
    schemas.WorkflowRatioSize.multiple_field_id
    schemas.WorkflowAutomaticSize.width_field_id
    schemas.WorkflowAutomaticSize.height_field_id
    schemas.WorkflowAutomaticSize.uses_reference
    schemas.WorkflowForm.parameter_controls
    schemas.WorkflowForm.parameter_presentation
    schemas.WorkflowForm.output_sizes
    schemas.WorkflowForm.reference_timelines
    schemas.WorkflowForm.image_crops
    schemas.WorkflowForm.shared_assets

    # The work-machine journal reads and writes these keys through dict literals and subscripts.
    RunRecord.clientId
    RunRecord.phase
    RunRecord.startedAt
    RunRecord.promptId
    WorkerState.claimId
    WorkerState.leaseSecret
    WorkerState.job
    WorkerState.runs
    WorkerState.index
    WorkerState.progress
    WorkerState.stage
    WorkerState.promptId
    WorkerState.sequence
    WorkerState.failure
    WorkerState.finishing

    # urllib invokes the redirect hook, which the Skill overrides to pin the API origin.
    HTTPRedirectHandler.redirect_request
    # uvicorn reads the shutdown flag set by tests that run a local HTTP server.
    Server.should_exit
    # zipfile reads the permission bits when it writes the entry.
    ZipInfo.external_attr
