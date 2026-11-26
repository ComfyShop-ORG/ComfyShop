"""目录列表和直接访问公共内容使用的可见条件。"""

from sqlalchemy import ColumnElement, or_

from comfyshop_api.models import Team, Work, Workflow
from comfyshop_api.services.worker_types import OFFICIAL

OFFICIAL_SOURCE_PREFIX = f"{OFFICIAL.kind}:platform:"


def public_catalog_workflow() -> ColumnElement[bool]:
    return Workflow.publicly_visible() & or_(
        Workflow.official_key.is_not(None),
        Workflow.remote_source.is_(None),
        ~Workflow.remote_source.startswith(OFFICIAL_SOURCE_PREFIX),
    )


def public_work_condition() -> ColumnElement[bool]:
    return (
        Work.visible()
        & Work.published.is_(True)
        & Team.active_scope(Work.team_id)
        & Workflow.publicly_visible()
    )
