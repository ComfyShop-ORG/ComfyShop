"""从停机后的 SQLite 数据卷备份导入一个空的 PostgreSQL 实例。"""

import argparse
import hashlib
import sys
import tarfile
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import BinaryIO

from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from comfyshop_api.core.config import Settings, get_settings
from comfyshop_api.db import Base, make_engine
from comfyshop_api.models import MediaObject, Status, Task, User
from comfyshop_media.storage import MediaStorage, original_key

_EPHEMERAL_TABLES = {
    "sessions",
    "password_resets",
    "auth_attempts",
    "machine_links",
    "official_worker_polls",
    "original_deletions",
}
_TASK_SOURCE_COLUMNS = ("source_execution_id", "source_work_id")


def _extract(archive_file: BinaryIO, directory: Path) -> None:
    """只提取数据库和原文件，缓存可由 API 重建。"""
    with tarfile.open(fileobj=archive_file, mode="r|*") as archive:
        for member in archive:
            parts = PurePosixPath(member.name).parts
            needed = parts in {("comfyshop.db",), ("comfyshop.db-wal",)} or (
                len(parts) == 2 and parts[0] == "originals" and not member.isdir()
            )
            if not needed:
                continue
            if (
                not member.isfile()
                or parts[-1] in {"..", "."}
                or (directory / member.name).exists()
            ):
                raise ValueError("备份包含无效或重复的原文件")
            archive.extract(member, directory, filter="data")
    if not (directory / "comfyshop.db").is_file():
        raise ValueError("备份须包含数据卷根目录下的 comfyshop.db")


def _originals(source: Connection, directory: Path) -> Iterator[tuple[str, Path, str, str]]:
    records = source.execute(
        select(
            MediaObject.storage_name, MediaObject.size, MediaObject.sha256, MediaObject.content_type
        )
    )
    for name, size, sha256, content_type in records:
        path = directory / original_key(name)
        if not path.is_file() or path.stat().st_size != size:
            raise ValueError("备份包含缺失的原文件或大小不一致")
        with path.open("rb") as media:
            if hashlib.file_digest(media, "sha256").hexdigest() != sha256:
                raise ValueError("备份中的原文件未通过 SHA-256 校验")
        yield name, path, content_type, sha256


def _copy_rows(source: Connection, target: Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    task_sources = {}
    for table in Base.metadata.sorted_tables:
        if table.name in _EPHEMERAL_TABLES:
            continue
        count = 0
        for batch in source.execute(select(table)).mappings().partitions(100):
            rows = [dict(row) for row in batch]
            if table.name == Task.__tablename__:
                # 任务可以引用之后才插入的执行组与作品。
                for row in rows:
                    values = {key: row.pop(key) for key in _TASK_SOURCE_COLUMNS}
                    if any(values.values()):
                        task_sources[row["id"]] = values
            if table.name == User.__tablename__:
                for row in rows:
                    row.update(
                        pending_email=None, pending_email_token=None, pending_email_expires_at=None
                    )
            target.execute(table.insert(), rows)
            count += len(rows)
        counts[table.name] = count
    task = Base.metadata.tables[Task.__tablename__]
    for task_id, values in task_sources.items():
        target.execute(task.update().where(task.c.id == task_id).values(**values))
    return counts


_LOCK_RESTORE = text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE")


def _import_backup(
    source: Connection, directory: Path, target_engine: Engine, storage: MediaStorage
) -> dict[str, int]:
    if source.exec_driver_sql("PRAGMA quick_check").scalars().all() != ["ok"]:
        raise ValueError("备份数据库完整性校验失败")
    if source.exec_driver_sql("PRAGMA foreign_key_check").first():
        raise ValueError("备份数据库存在失效引用")
    if source.scalar(select(Task.id).where(Task.status.in_(Status.ACTIVE)).limit(1)):
        raise ValueError("备份仍有待领取或运行中的任务")
    originals = list(_originals(source, directory))
    copied = []
    transaction_id: int | None = None
    counts: dict[str, int] = {}
    try:
        with target_engine.begin() as target:
            target.execute(_LOCK_RESTORE)
            if any(
                target.scalar(select(1).select_from(table).limit(1))
                for table in Base.metadata.tables.values()
            ):
                raise ValueError("目标数据库须为已迁移的空库")
            existing = storage.restore_inventory([name for name, *_ in originals])
            counts = _copy_rows(source, target)
            for name, path, content_type, sha256 in originals:
                if name in existing:
                    if not storage.original_matches(name, path.stat().st_size, sha256):
                        raise ValueError("目标存储中已有的原件与备份不符")
                else:
                    storage.put(name, path, content_type)
                    copied.append(name)
            transaction_id = target.scalar(text("SELECT txid_current()"))
        return counts
    except BaseException as error:
        if copied or transaction_id is not None:
            # COMMIT 的回复可能丢失。重新取得恢复锁，保留已经登记或被其他恢复复用的文件。
            try:
                with target_engine.begin() as check:
                    check.execute(_LOCK_RESTORE)
                    if isinstance(error, SQLAlchemyError) and transaction_id is not None:
                        status = check.scalar(
                            text("SELECT txid_status(:id)"), {"id": transaction_id}
                        )
                        if status == "committed":
                            return counts
                    registered = set(check.scalars(select(MediaObject.storage_name)))
                    for name in copied:
                        if name not in registered:
                            storage.delete(name)
            except (OSError, SQLAlchemyError):
                print("暂时无法核对目标存储，重试时将校验已有原件", file=sys.stderr)
        raise


def restore(archive: BinaryIO, settings: Settings, alembic_ini: Path) -> dict[str, int]:
    target_engine = make_engine(settings.database_dsn)
    try:
        if target_engine.dialect.name != "postgresql":
            raise ValueError("恢复目标须为 PostgreSQL")
        with TemporaryDirectory(prefix="comfyshop-restore-") as temporary:
            directory = Path(temporary)
            _extract(archive, directory)
            source_url = f"sqlite:///{directory / 'comfyshop.db'}"
            source_config = Config(str(alembic_ini))
            source_config.attributes["database_url"] = source_url
            command.upgrade(source_config, "head")
            source_engine = make_engine(source_url)
            try:
                with source_engine.connect() as source:
                    return _import_backup(source, directory, target_engine, settings.media_storage)
            finally:
                source_engine.dispose()
    finally:
        target_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", help="数据卷 tar/tar.gz 备份，使用 - 从标准输入读取")
    parser.add_argument("--alembic-config", type=Path, default=Path("apps/api/alembic.ini"))
    args = parser.parse_args()
    settings = get_settings()
    if args.archive == "-":
        counts = restore(sys.stdin.buffer, settings, args.alembic_config)
    else:
        with Path(args.archive).open("rb") as archive:
            counts = restore(archive, settings, args.alembic_config)
    for table, count in counts.items():
        print(f"{table}: {count}")


if __name__ == "__main__":
    main()
