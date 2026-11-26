"""合并公开目录，保留旧记录和各版官方工作流的译文。"""

import hashlib
import json

import sqlalchemy as sa
from alembic import op

revision = "490d562f6d9c"
down_revision = "1d8772cd83d3"
branch_labels = None
depends_on = None


def _collect_translations() -> None:
    workflows = sa.table(
        "workflows",
        sa.column("id"),
        sa.column("official_key"),
        sa.column("site"),
        sa.column("name"),
        sa.column("description"),
    )
    versions = sa.table(
        "workflow_versions",
        sa.column("id"),
        sa.column("workflow_id"),
        sa.column("number"),
        sa.column("graph", sa.JSON()),
        sa.column("translations", sa.JSON()),
    )
    db = op.get_bind()
    texts_by_graph = {}
    rows = []
    for row in db.execute(
        sa.select(
            versions.c.id,
            workflows.c.official_key,
            workflows.c.site,
            workflows.c.name,
            workflows.c.description,
            versions.c.graph,
        )
        .select_from(versions.join(workflows, versions.c.workflow_id == workflows.c.id))
        .where(workflows.c.official_key.is_not(None))
        .order_by(versions.c.number, versions.c.id)
    ):
        graph = row.graph
        fields = graph.get("fields", [])
        layout = graph.get("parameter_layout", [])
        shape = {
            **graph,
            "fields": [
                {
                    key: value
                    for key, value in field.items()
                    if key not in {"label", "choice_labels"}
                }
                for field in fields
            ],
            "parameter_layout": [
                {key: value for key, value in entry.items() if key not in {"display_name", "help"}}
                for entry in layout
            ],
        }
        fingerprint = hashlib.sha256(json.dumps(shape, sort_keys=True).encode()).digest()
        key = row.official_key, fingerprint
        text = {
            "name": row.name,
            "description": row.description,
            "fields": {
                field["name"]: {
                    name: field[name] for name in ("label", "choice_labels") if field.get(name)
                }
                for field in fields
                if field.get("label") or field.get("choice_labels")
            },
            "parameter_layout": {
                entry["field_id"]: {
                    name: entry[name] for name in ("display_name", "help") if entry.get(name)
                }
                for entry in layout
                if entry.get("display_name") or entry.get("help")
            },
        }
        texts_by_graph.setdefault(key, {})[row.site] = text
        rows.append((row.id, key, row.site, text))
    for version_id, key, language, text in rows:
        db.execute(
            versions.update()
            .where(versions.c.id == version_id)
            .values(translations=texts_by_graph[key] | {language: text})
        )


def upgrade() -> None:
    op.add_column(
        "workflow_versions", sa.Column("translations", sa.JSON(none_as_null=True), nullable=True)
    )
    _collect_translations()
    # 保留旧工作流、版本及其链接。每个官方标识只留一个目录入口。
    op.execute(
        """
        UPDATE workflows
        SET official_key = NULL
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY official_key ORDER BY
                    CASE WHEN deleted_at IS NULL THEN 0 ELSE 1 END,
                    CASE WHEN published THEN 0 ELSE 1 END,
                    CASE WHEN site = 'zh' THEN 0 ELSE 1 END,
                    updated_at DESC, id
                ) AS position
                FROM workflows WHERE official_key IS NOT NULL
            ) AS ranked
            WHERE position > 1
        )
        """
    )
    for index in (
        "ix_workflows_remote_source",
        "ix_workflows_site_official_key",
        "ix_workflows_site_public_updated",
    ):
        op.drop_index(index, table_name="workflows")
    op.drop_column("workflows", "site")
    op.create_index("ix_workflows_remote_source", "workflows", ["owner_id", "remote_source"])
    op.create_index("ix_workflows_official_key", "workflows", ["official_key"], unique=True)
    op.create_index(
        "ix_workflows_public_updated", "workflows", ["published", "deleted_at", "updated_at", "id"]
    )


def downgrade() -> None:
    for index in (
        "ix_workflows_remote_source",
        "ix_workflows_official_key",
        "ix_workflows_public_updated",
    ):
        op.drop_index(index, table_name="workflows")
    op.add_column(
        "workflows", sa.Column("site", sa.String(32), nullable=False, server_default="zh")
    )
    op.create_index(
        "ix_workflows_remote_source", "workflows", ["owner_id", "site", "remote_source"]
    )
    op.create_index(
        "ix_workflows_site_official_key", "workflows", ["site", "official_key"], unique=True
    )
    op.create_index(
        "ix_workflows_site_public_updated",
        "workflows",
        ["site", "published", "deleted_at", "updated_at", "id"],
    )
    op.drop_column("workflow_versions", "translations")
