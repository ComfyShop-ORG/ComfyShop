from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, Table, inspect, select
from sqlalchemy.exc import IntegrityError

from comfyshop_api.core.config import Settings
from comfyshop_api.db import Base, make_engine
from comfyshop_api.main import create_app


@pytest.mark.parametrize("dialect", ["sqlite", "postgresql"])
def test_empty_database_migration_round_trip(dialect, tmp_path, request):
    url = (
        f"sqlite:///{tmp_path / 'schema.db'}"
        if dialect == "sqlite"
        else request.getfixturevalue("pg_url")
    )
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.attributes["database_url"] = url
    engine = make_engine(url)
    try:
        command.upgrade(config, "head")
        command.check(config)
        # 任务引用执行和作品，两个表又引用任务。核对两类数据库实际建立的外键。
        sources = {
            (tuple(fk["constrained_columns"]), fk["referred_table"])
            for fk in inspect(engine).get_foreign_keys("tasks")
        }
        assert (("source_execution_id",), "executions") in sources
        assert (("source_work_id",), "works") in sources

        command.downgrade(config, "base")
        assert inspect(engine).get_table_names() == ["alembic_version"]
        command.upgrade(config, "head")
        assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables) | {
            "alembic_version"
        }
    finally:
        engine.dispose()


@pytest.mark.parametrize("dialect", ["sqlite", "postgresql"])
def test_catalog_migration_preserves_old_versions_and_merges_display_text(
    dialect, tmp_path, request
):
    url = (
        f"sqlite:///{tmp_path / 'catalog.db'}"
        if dialect == "sqlite"
        else request.getfixturevalue("pg_url")
    )
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, "1d8772cd83d3")
    engine = make_engine(url)
    metadata = MetaData()
    users = Table("users", metadata, autoload_with=engine)
    workflows = Table("workflows", metadata, autoload_with=engine)
    versions = Table("workflow_versions", metadata, autoload_with=engine)
    names = {"zh": "旧版模型", "en": "Original model", "ja": "旧モデル"}
    graph_by_locale = {}
    records = []
    try:
        with engine.begin() as conn:
            conn.execute(
                users.insert(),
                {
                    "id": "owner",
                    "username": "Author",
                    "username_key": "author",
                    "password_hash": "unused",
                    "created_at": 1,
                },
            )
            for timestamp, language in enumerate(("zh", "ja", "en"), 1):
                name = names[language]
                graph = {
                    "fields": [
                        {
                            "name": "quality",
                            "kind": "choice",
                            "label": name,
                            "choices": ["original"],
                            "choice_labels": {"original": name},
                            "default": "original",
                        }
                    ],
                    "parameter_layout": [{"field_id": "quality", "help": name}],
                    "execution": {"config": {"model": "original"}},
                }
                graph_by_locale[language] = graph
                record = {
                    "id": f"workflow-{language}",
                    "owner_id": "owner",
                    "site": language,
                    "name": name,
                    "category": "image",
                    "description": name,
                    "published": language != "zh",
                    "published_version_id": f"version-{language}" if language != "zh" else None,
                    "official_key": "original",
                    "remote_source": "official:platform:original",
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
                records.append(record)
                conn.execute(workflows.insert(), record)
                conn.execute(
                    versions.insert(),
                    {
                        "id": f"version-{language}",
                        "workflow_id": record["id"],
                        "number": 1,
                        "graph": graph,
                        "graph_hash": f"hash-{language}",
                        "format": "service",
                        "worker_kind": "official",
                        "requirements": [],
                        "published": record["published"],
                        "created_at": timestamp,
                    },
                )

        command.upgrade(config, "head")
        command.check(config)
        upgraded = MetaData()
        workflows = Table("workflows", upgraded, autoload_with=engine)
        versions = Table("workflow_versions", upgraded, autoload_with=engine)
        assert "site" not in workflows.c
        with engine.connect() as conn:
            for record in records:
                language = record["site"]
                workflow = conn.execute(
                    select(workflows).where(workflows.c.id == record["id"])
                ).one()
                assert workflow.official_key == ("original" if language == "en" else None)
                assert workflow.published_version_id == record["published_version_id"]
                version = conn.execute(
                    select(versions).where(versions.c.workflow_id == workflow.id)
                ).one()
                assert version.id == f"version-{language}"
                assert version.graph_hash == f"hash-{language}"
                assert version.graph == graph_by_locale[language]
                assert {
                    code: entry["name"] for code, entry in version.translations.items()
                } == names
                for code, entry in version.translations.items():
                    assert entry["fields"]["quality"]["choice_labels"] == {"original": names[code]}
                    assert entry["parameter_layout"]["quality"]["help"] == names[code]
        duplicate = dict(records[-1], id="duplicate")
        del duplicate["site"]
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(workflows.insert(), duplicate)

        settings = Settings(database_url=url, data_dir=tmp_path / "media", static_dir=None)
        with TestClient(create_app(settings)) as client:
            for language, name in names.items():
                headers = {"Accept-Language": language}
                response = client.get("/api/v1/workflows", headers=headers, params={"search": name})
                [workflow] = response.raise_for_status().json()["items"]
                assert (workflow["id"], workflow["name"]) == ("workflow-en", name)
            historical = client.get(
                "/api/v1/workflows/workflow-ja", params={"version_id": "version-ja"}
            )
            assert historical.raise_for_status().json()["versionId"] == "version-ja"
            assert client.get("/api/v1/workflows/workflow-zh").status_code == 404
    finally:
        engine.dispose()
