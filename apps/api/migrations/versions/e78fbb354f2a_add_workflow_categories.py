"""将工作流分类扩充为官方八类。"""

from alembic import op
import sqlalchemy as sa

revision = "e78fbb354f2a"
down_revision = "c4a1e35e62f9"
branch_labels = None
depends_on = None

workflows = sa.table(
    "workflows",
    sa.column("id", sa.String),
    sa.column("category", sa.String),
    sa.column("published_version_id", sa.String),
)
versions = sa.table(
    "workflow_versions",
    sa.column("id", sa.String),
    sa.column("workflow_id", sa.String),
    sa.column("number", sa.Integer),
    sa.column("requirements", sa.JSON),
)


def upgrade() -> None:
    with op.batch_alter_table("workflows") as batch:
        batch.drop_constraint("workflow_category", type_="check")
    # 旧工具类按公开版本（无公开版本时按最新草稿）的明确节点类型归类。
    published = (
        sa.select(versions.c.requirements)
        .where(versions.c.id == workflows.c.published_version_id)
        .scalar_subquery()
    )
    latest = (
        sa.select(versions.c.requirements)
        .where(versions.c.workflow_id == workflows.c.id)
        .order_by(versions.c.number.desc())
        .limit(1)
        .scalar_subquery()
    )
    requirements = sa.func.coalesce(published, latest, type_=sa.JSON)
    connection = op.get_bind()
    legacy = connection.execute(
        sa.select(workflows.c.id, requirements).where(workflows.c.category == "tool")
    ).all()
    markers = (
        ("3d", {"Save3DAdvanced", "SaveGLB"}),
        ("audio", {"SaveAudioAdvanced", "SaveAudio", "SaveAudioMP3", "SaveAudioOpus"}),
        ("vector", {"SaveSVG"}),
        ("video_tool", {"LoadVideo", "SaveVideo", "VHS_LoadVideo", "VHS_VideoCombine"}),
    )
    for workflow_id, nodes in legacy:
        known = set(nodes or [])
        category = next((value for value, types in markers if known & types), "image_tool")
        connection.execute(
            workflows.update().where(workflows.c.id == workflow_id).values(category=category)
        )
    with op.batch_alter_table("workflows") as batch:
        batch.create_check_constraint(
            "workflow_category",
            "category IN ('image','image_tool','video','video_tool','audio','3d','vector','llm')",
        )


def downgrade() -> None:
    with op.batch_alter_table("workflows") as batch:
        batch.drop_constraint("workflow_category", type_="check")
    op.execute(
        workflows.update()
        .where(workflows.c.category.not_in(("image", "video")))
        .values(category="tool")
    )
    with op.batch_alter_table("workflows") as batch:
        batch.create_check_constraint("workflow_category", "category IN ('image','video','tool')")
