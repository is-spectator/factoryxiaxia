"""0003: 空空 OpenClaw 运行时结构。"""

from sqlalchemy import inspect

from migration_manager import ensure_column, ensure_index


VERSION = "0003"
NAME = "kongkong_runtime"


def _ensure_kongkong_table(connection, app_module):
    inspector = inspect(connection)
    if "kongkong_instances" in inspector.get_table_names():
        return
    app_module.KongKongInstance.__table__.create(bind=connection, checkfirst=True)


def upgrade(connection, app_module):
    column_specs = [
        ("workers", "runtime_kind", "VARCHAR(40) DEFAULT 'none'"),
        ("service_plans", "instance_type", "VARCHAR(40) DEFAULT 'standard'"),
        ("service_plans", "cpu_limit", "DECIMAL(6,2) DEFAULT 1.0"),
        ("service_plans", "memory_limit_mb", "INTEGER DEFAULT 2048"),
        ("service_plans", "storage_limit_gb", "INTEGER DEFAULT 10"),
    ]
    for table_name, column_name, column_sql in column_specs:
        ensure_column(connection, table_name, column_name, column_sql)

    _ensure_kongkong_table(connection, app_module)

    index_specs = [
        ("workers", "idx_workers_runtime_kind", ["runtime_kind"], False),
        ("kongkong_instances", "idx_kongkong_instances_user_id", ["user_id"], False),
        ("kongkong_instances", "idx_kongkong_instances_status", ["status"], False),
        ("kongkong_instances", "idx_kongkong_instances_slug", ["instance_slug"], False),
    ]
    for table_name, index_name, columns, unique in index_specs:
        ensure_index(connection, table_name, index_name, columns, unique=unique)
