from logging.config import fileConfig

from alembic import context

from comfyshop_api import models  # noqa: F401 -- registers all tables for Alembic
from comfyshop_api.core.config import get_settings
from comfyshop_api.db import Base, make_engine

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name, disable_existing_loggers=False)
target_metadata = Base.metadata
url = config.attributes.get("database_url") or get_settings().database_dsn

if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = make_engine(url)
    with engine.connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        if sqlite:
            # SQLite batch replacement needs referencing tables to survive the
            # copy/drop/rename cycle. Validate all links before committing.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                transactional_ddl=True if sqlite else None,
            )
            with context.begin_transaction():
                context.run_migrations()
            if sqlite:
                if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchone():
                    raise RuntimeError("数据库迁移出现无效外键，已回滚")
                connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            if sqlite:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()
    engine.dispose()
