"""创建数据库引擎，提供每个 API 请求独立使用的数据库会话。"""

from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine, event, inspect, update
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    """用 SQLAlchemy 连接地址创建引擎，SQLite 启用外键校验、WAL 和写锁等待。"""
    parsed = make_url(url)
    if parsed.drivername.startswith("sqlite"):
        from pathlib import Path

        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 15})

        @event.listens_for(engine, "connect")
        def configure_sqlite(connection: DBAPIConnection, _record: object) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        return engine
    return create_engine(url, pool_pre_ping=True)


def write_lock(db: Session, model: type[Base], record_id: str) -> None:
    """在当前事务里取得写锁，保持到提交或回滚，用来串行化“先检查再写入”的操作。

    实现是把主键更新为自身，不改变任何数据。SQLite 上这会锁住整个数据库的写入，
    其他数据库上锁住这一行。它看起来没有效果，但删除后并发请求会各自通过检查。
    """
    key = inspect(model).primary_key[0]
    db.execute(
        update(model)
        .where(key == record_id)
        .values({key.name: key})
        .execution_options(synchronize_session=False)
    )


def get_db(request: Request) -> Generator[Session, None, None]:
    """使用当前应用的引擎打开会话，请求结束后关闭。写入由调用方显式提交。"""
    with Session(request.app.state.engine, expire_on_commit=False) as session:
        yield session
