"""Static references for framework consumers; never imported by application code."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from urllib.request import HTTPRedirectHandler
    from xml.parsers.expat import XMLParserType
    from zipfile import ZipInfo

    from uvicorn import Server

    from comfyshop_api import schemas
    from comfyshop_api.api.health import HealthResponse
    from comfyshop_api.core.categories import WorkflowCategory
    from comfyshop_api.core.config import Settings
    from comfyshop_official_worker.atlas_cloud import CompositionChunk
    from comfyshop_official_worker.quotes import UnitQuote
    from comfyshop_worker.config import RecoveryRecord, RunRecord, WorkerState

    # Pydantic reads model configuration and serializes these fields dynamically.
    WorkflowCategory.IMAGE_TOOL
    WorkflowCategory.VIDEO
    WorkflowCategory.VIDEO_TOOL
    WorkflowCategory.AUDIO
    WorkflowCategory.MODEL_3D
    WorkflowCategory.VECTOR
    WorkflowCategory.LLM
    WorkflowCategory.NODE_BASICS
    WorkflowCategory.PRODUCT_ADS
    WorkflowCategory.CHARACTER_FASHION
    WorkflowCategory.BRAND_DESIGN
    Settings.model_config
    HealthResponse.service
    schemas.AuthorRead.avatar_url
    schemas.MediaRead.src
    schemas.MediaRead.video_preview
    schemas.WorkflowRead.author
    schemas.WorkflowRead.author_profile
    schemas.WorkflowVersions.current_version_id
    schemas.WorkspaceRead.favorite_ids
    schemas.WorkspaceRead.can_manage_official_import_grants
    schemas.TeamEventRead.actor_name
    schemas.TeamEventRead.actor_username
    schemas.AssetUsage.used_bytes
    schemas.AssetUsage.remaining_bytes
    schemas.AssetUsage.limit_bytes
    schemas.CostEstimate.unit_price
    schemas.CostEstimate.currency
    schemas.CostEstimate.serialize_price
    schemas.TaskActivity.active_tasks
    schemas.TaskActivity.completed_executions
    schemas.TaskProgressRead.takeover_history
    schemas.WorkerRoute.imports_reference
    schemas.JobRead.worker_context
    schemas.MachineRead.online
    schemas.MachineRead.busy
    schemas.MachineRead.revoked
    schemas.MachineRead.node_count
    schemas.MachineRead.update_available
    schemas.MachinePage.worker_release
    schemas.MachineHeartbeat.protocol_version
    schemas.JobRead.prompt_preview_node_id
    schemas.ExecutionRead.task_owner_id
    schemas.ExecutionRead.prompt_expanded
    schemas.ExecutionRead.image_count
    schemas.ExecutionRead.video_count
    schemas.ExecutionRead.audio_count
    schemas.ExecutionRead.model_count
    schemas.ExecutionRead.text_count
    schemas.ExecutionRead.artifact_count
    schemas.WorkRead.asset_count
    schemas.WorkRead.author_profile
    schemas.NodeInput.multiline
    schemas.WorkflowInput.primary
    schemas.WorkflowInput.named
    schemas.MachineLinkStart.expires_in
    schemas.MachineLinkStart.interval
    schemas.MachineLinkStart.verification_path
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
    schemas.TaskInputsRead.comparisons
    schemas.OutputComparison.uniform_upscale
    schemas.WorkflowMask.channel_field_id
    schemas.WorkflowForm.parameter_controls
    schemas.WorkflowForm.parameter_presentation
    schemas.WorkflowForm.output_sizes
    schemas.WorkflowForm.reference_timelines
    schemas.WorkflowForm.image_crops
    schemas.WorkflowForm.shared_assets
    schemas.WorkflowFormData.cost_estimate
    schemas.ServiceJobRead.event_sequence
    schemas.OfficialExecution.adapter
    schemas.OfficialExecution.output_kind
    CompositionChunk.positive_styles
    CompositionChunk.negative_styles
    CompositionChunk.context_adherence
    UnitQuote.unitPrice
    UnitQuote.currency

    # The work-machine journal reads and writes these keys through dict literals and subscripts.
    RunRecord.clientId
    RunRecord.phase
    RunRecord.startedAt
    RunRecord.executionStarted
    RunRecord.promptId
    RunRecord.promptPreviewNodeId
    RunRecord.effectivePrompt
    RunRecord.uploadedClientIds
    RecoveryRecord.taskId
    RecoveryRecord.expiresAt
    WorkerState.claimId
    WorkerState.leaseSecret
    WorkerState.job
    WorkerState.runs
    WorkerState.uploadedAssets
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
    # Expat invokes these handlers while parsing SVG exports.
    XMLParserType.StartElementHandler
    XMLParserType.StartDoctypeDeclHandler
