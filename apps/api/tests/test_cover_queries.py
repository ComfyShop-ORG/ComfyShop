from uuid import uuid4

import pytest
from helpers import task_body
from sqlalchemy import event, select, update
from sqlalchemy.orm import Session

from comfyshop_api.models import (
    Artifact,
    Execution,
    MediaObject,
    Status,
    Task,
    Work,
    WorkArtifact,
    Workflow,
)
from comfyshop_api.services.tasks import task_covers
from comfyshop_api.services.workflows import workflow_covers


@pytest.fixture
def cover_history(authenticated, graph):
    """四个工作流各有两次成功执行和 180 份成品，只有第一个有公开作品。"""
    client = authenticated
    owner = client.get("/api/v1/auth/session").json()["user"]["id"]
    workflows, tasks, outputs, works = [], [], {}, []
    for position in range(4):
        workflow = client.post(
            "/api/v1/workflows", json={"name": f"history-{position}", "graph": graph}
        ).json()
        body = task_body(client, workflow)
        task = client.post("/api/v1/tasks", json={**body, "executionCount": 2}).json()
        workflows.append(workflow["id"])
        tasks.append(task["id"])
        with Session(client.app.state.engine) as db:
            record = db.get(Task, task["id"])
            record.status, record.progress = Status.SUCCEEDED, 100
            executions = db.scalars(
                select(Execution).where(Execution.task_id == record.id).order_by(Execution.index)
            ).all()
            media = {
                kind: MediaObject(
                    sha256=uuid4().hex * 2,
                    storage_name=uuid4().hex,
                    size=100,
                    content_type=kind,
                    width=32,
                    height=48,
                )
                for kind in ("video/mp4", "image/png")
            }
            members = []
            for index, execution in enumerate(executions):
                execution.status = Status.SUCCEEDED
                execution.created_at = 1000 + index
                group = []
                for offset in range(20 if index == 0 else 160):
                    original = media["image/png" if offset else "video/mp4"]
                    artifact = Artifact(
                        id=str(uuid4()),
                        owner_id=owner,
                        task_id=record.id,
                        execution_id=execution.id,
                        client_id=str(uuid4()),
                        filename="output.png",
                        content_type=original.content_type,
                        media=original,
                        output_index=offset,
                    )
                    db.add(artifact)
                    group.append(artifact)
                execution.manifest = [artifact.client_id for artifact in group]
                members.extend(group)
            db.flush()
            outputs[record.id] = [artifact.id for artifact in members]
            if position == 0:
                for index, artifact in enumerate(members):
                    work = Work(
                        id=str(uuid4()),
                        owner_id=owner,
                        workflow_id=workflow["id"],
                        version_id=workflow["versionId"],
                        execution_id=artifact.execution_id,
                        title="work",
                        request_hash="0" * 64,
                        cover_artifact_id=artifact.id,
                        created_at=index,
                        published=index != len(members) - 2,
                        deleted_at=1 if index == len(members) - 1 else None,
                    )
                    db.add(work)
                    db.flush()
                    db.add(WorkArtifact(work_id=work.id, artifact_id=artifact.id, position=0))
                    works.append(work.id)
            db.commit()
        if position == 0:
            assert client.post(f"/api/v1/workflows/{workflow['id']}/publish").status_code == 200
    return client.app.state.engine, owner, workflows, tasks, outputs, works


def measure_reads(db, operation):
    """只观察本次读取的连接，记录 SQL 次数和实际加载的成品，排除后台维护。"""
    loaded, statements = [], []
    connection = db.connection()

    def on_load(_session, record):
        if isinstance(record, Artifact):
            loaded.append(record.id)

    def on_select(_connection, _cursor, statement, parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append((statement, parameters))

    event.listen(db, "loaded_as_persistent", on_load)
    event.listen(connection, "before_cursor_execute", on_select)
    try:
        result = operation()
    finally:
        event.remove(db, "loaded_as_persistent", on_load)
        event.remove(connection, "before_cursor_execute", on_select)
    return result, loaded, statements


@pytest.mark.parametrize("as_owner", [False, True], ids=["public", "owner"])
def test_workflow_cover_reads_are_bounded_by_the_current_page(cover_history, as_owner):
    engine, owner, workflow_ids, task_ids, outputs, _works = cover_history
    with Session(engine) as db:
        workflows = db.scalars(select(Workflow).where(Workflow.id.in_(workflow_ids))).all()
        covers, loaded, statements = measure_reads(
            db, lambda: workflow_covers(db, workflows, owner if as_owner else None)
        )
        assert len(covers) == len(loaded) == (4 if as_owner else 1)
        assert len(statements) == (2 if as_owner else 1)
        # 最近一份已删除、倒数第二份未公开，均不能充当封面。
        assert outputs[task_ids[0]][-3] in covers[workflow_ids[0]].src
        for workflow_id, task_id in zip(workflow_ids[1:], task_ids[1:], strict=True):
            if as_owner:
                # 最新一次执行优先图片，跳过排在最前面的视频。
                assert outputs[task_id][21] in covers[workflow_id].src
            else:
                assert workflow_id not in covers
        # 不绑定具体索引名；约束公开封面通过查找取首项，不扫描或排序作品历史。
        if not as_owner:
            statement, parameters = statements[0]
            plan = "\n".join(
                row[3]
                for row in db.connection().exec_driver_sql(
                    "EXPLAIN QUERY PLAN " + statement, parameters
                )
            )
            assert "SEARCH works" in plan
            assert "SCAN works" not in plan
            assert "TEMP B-TREE" not in plan
        else:
            # 私有封面从这个工作流自己的任务出发，不沿全平台的成功执行逐条比对。
            statement, parameters = statements[1]
            plan = "\n".join(
                row[3]
                for row in db.connection().exec_driver_sql(
                    "EXPLAIN QUERY PLAN " + statement, parameters
                )
            )
            assert "SEARCH tasks USING INDEX ix_tasks_workflow_owner" in plan
            assert "(status=?)" not in plan
            assert "SCAN executions" not in plan


def test_task_cover_reads_do_not_expand_all_outputs(cover_history):
    engine, _owner, _workflow_ids, task_ids, outputs, _works = cover_history
    with Session(engine) as db:
        tasks = db.scalars(select(Task).where(Task.id.in_(task_ids))).all()
        covers, loaded, statements = measure_reads(db, lambda: task_covers(db, tasks))
        assert len(covers) == len(loaded) == len(tasks)
        assert len(statements) == 1
        for task_id in task_ids:
            assert outputs[task_id][1] in covers[task_id].src
        # 还没有完整确认的执行不能给出一个会返回 404 的封面。
        db.execute(
            update(Execution).where(Execution.task_id == task_ids[0]).values(status=Status.RUNNING)
        )
        db.commit()
        assert task_ids[0] not in task_covers(db, tasks)


def test_pinned_cover_is_selected_without_loading_other_work_media(cover_history):
    engine, _owner, workflow_ids, task_ids, outputs, works = cover_history
    with Session(engine) as db:
        workflow = db.get(Workflow, workflow_ids[0])
        workflow.cover_work_id = works[0]
        db.commit()
        db.refresh(workflow)
        covers, loaded, statements = measure_reads(
            db, lambda: workflow_covers(db, [workflow], None)
        )
        assert outputs[task_ids[0]][0] in covers[workflow.id].src
        assert loaded == [outputs[task_ids[0]][0]]
        assert len(statements) == 1
