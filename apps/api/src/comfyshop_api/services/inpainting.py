"""Find runnable image/mask pairs from the same version and machine forms used for generation."""

from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session, undefer

from comfyshop_api.models import Machine, Workflow, WorkflowVersion, now_ms
from comfyshop_api.schemas import InpaintTarget
from comfyshop_api.security import workspace_records
from comfyshop_api.services.artifacts import completed_artifact
from comfyshop_api.services.inputs import form_for, localize_form
from comfyshop_api.services.machines import machine_is_online, machine_preference, machine_scope
from comfyshop_api.services.parameter_features import INPAINT_NODES
from comfyshop_api.services.public_catalog import public_catalog_workflow
from comfyshop_api.services.workflows import browse_version_id, can_read_workflow_drafts


def inpaint_targets(
    db: Session,
    user_id: str,
    team_id: str | None,
    language: str,
    artifact_id: str,
) -> list[InpaintTarget]:
    artifact, task = completed_artifact(db, artifact_id, user_id, team_id)
    own = workspace_records(Workflow.owner_id, Workflow.team_id, user_id, team_id)
    # A personal source execution already grants its operator read access to that version.
    # Team tasks can use their own drafts and other workflows' published versions.
    source_version = WorkflowVersion.id == task.version_id
    allowed_source = (
        source_version
        if team_id is None
        else source_version & (own | WorkflowVersion.published.is_(True))
    )
    versions = db.execute(
        select(Workflow, WorkflowVersion)
        .join(WorkflowVersion, WorkflowVersion.workflow_id == Workflow.id)
        .where(
            Workflow.visible(),
            (WorkflowVersion.id == browse_version_id(own)) | allowed_source,
            own | public_catalog_workflow(),
            WorkflowVersion.format == "api",
            WorkflowVersion.worker_kind == "comfyui",
            or_(
                *(
                    cast(WorkflowVersion.requirements, String).contains(f'"{kind}"')
                    for kind in INPAINT_NODES
                )
            ),
        )
        .options(
            undefer(WorkflowVersion.graph),
            undefer(WorkflowVersion.parameter_layout),
            undefer(WorkflowVersion.worker_data),
        )
        .order_by(source_version.desc(), own.desc(), Workflow.updated_at.desc(), Workflow.id)
    ).all()
    if not versions:
        return []
    machines = db.scalars(
        select(Machine)
        .where(
            machine_scope(user_id, team_id),
            Machine.visible(),
            Machine.revoked_at.is_(None),
            Machine.worker_kind == "comfyui",
            Machine.catalog_synced_at.is_not(None),
        )
        .options(undefer(Machine.catalog))
    ).all()
    pref = machine_preference(db, user_id, team_id)
    now = now_ms()
    ordered = sorted(
        machines,
        key=lambda m: (
            not machine_is_online(m.last_seen, m.revoked_at, now) or m.paused,
            m.id != (pref.default_machine_id if pref else None),
            m.name,
            m.id,
        ),
    )
    targets = []
    matched_workflows: set[str] = set()
    for workflow, version in versions:
        if workflow.id in matched_workflows:
            continue
        seen: set[str] = set()
        for machine in ordered:
            if not machine.catalog or machine.connection_scope != version.connection_scope:
                continue
            form = form_for(version, machine)
            if form.issues:
                continue
            localize_form(form, language, version=version)
            labels = {entry.field_id: entry.display_name for entry in form.parameter_layout}
            for field in form.fields:
                if field.id in seen or artifact.content_type not in (
                    field.accepted_content_types or []
                ):
                    continue
                display = form.parameter_presentation.get(field.id)
                if not display or not (mask := display.mask):
                    continue
                seen.add(field.id)
                targets.append(
                    InpaintTarget(
                        workflow_id=workflow.id,
                        scope="mine"
                        if can_read_workflow_drafts(workflow, user_id, team_id)
                        else "public",
                        version_id=version.id,
                        machine_id=machine.id,
                        field_id=field.id,
                        label=labels.get(field.id) or field.label,
                        mask=mask,
                    )
                )
        if seen:
            matched_workflows.add(workflow.id)
    return targets
