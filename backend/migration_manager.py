"""数据库迁移管理器。"""

from importlib import import_module
from pathlib import Path

from sqlalchemy import inspect, text


MIGRATIONS_PACKAGE = "migrations.versions"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations" / "versions"


def _truthy(value):
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def load_migration_modules():
    modules = []
    for path in sorted(MIGRATIONS_DIR.glob("v*.py")):
        if path.name == "__init__.py":
            continue
        module = import_module(f"{MIGRATIONS_PACKAGE}.{path.stem}")
        modules.append(module)
    modules.sort(key=lambda module: module.VERSION)
    return modules


def ensure_migration_table(engine):
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(40) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))


def get_applied_migrations(engine):
    ensure_migration_table(engine)
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT version, name, applied_at FROM schema_migrations ORDER BY version ASC")
        ).mappings().all()
    return [dict(row) for row in rows]


def get_pending_migrations(engine):
    applied_versions = {row["version"] for row in get_applied_migrations(engine)}
    return [
        module for module in load_migration_modules()
        if module.VERSION not in applied_versions
    ]


def apply_migrations(app_module):
    engine = app_module.db.engine
    ensure_migration_table(engine)
    applied_versions = {row["version"] for row in get_applied_migrations(engine)}

    applied = []
    for module in load_migration_modules():
        if module.VERSION in applied_versions:
            continue
        with engine.begin() as connection:
            module.upgrade(connection, app_module)
            connection.execute(
                text(
                    "INSERT INTO schema_migrations (version, name) "
                    "VALUES (:version, :name)"
                ),
                {"version": module.VERSION, "name": module.NAME},
            )
        applied.append({"version": module.VERSION, "name": module.NAME})
    return applied


def describe_migration_state(app_module):
    engine = app_module.db.engine
    applied = get_applied_migrations(engine)
    pending = [
        {"version": module.VERSION, "name": module.NAME}
        for module in get_pending_migrations(engine)
    ]
    return {"applied": applied, "pending": pending}


def validate_migration_state(app_module, app_env=None, env_map=None):
    env_map = env_map or {}
    app_env = (app_env or env_map.get("APP_ENV") or "development").strip().lower()
    if app_env == "test" or _truthy(env_map.get("SKIP_MIGRATION_CHECK")):
        return True

    state = describe_migration_state(app_module)
    if state["pending"]:
        pending_text = ", ".join(
            f"{item['version']}:{item['name']}" for item in state["pending"]
        )
        raise RuntimeError(
            "检测到未执行的数据库迁移，请先运行 `python manage.py migrate` 后再启动服务。"
            f" 待执行迁移: {pending_text}"
        )
    return True


def ensure_column(connection, table_name, column_name, column_sql):
    inspector = inspect(connection)
    if table_name not in inspector.get_table_names():
        return False
    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in existing_columns:
        return False
    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"))
    return True


def ensure_index(connection, table_name, index_name, columns, unique=False):
    inspector = inspect(connection)
    normalized_columns = tuple(columns)
    existing_indexes = inspector.get_indexes(table_name)
    for index in existing_indexes:
        if index.get("name") == index_name:
            return False
        if tuple(index.get("column_names") or []) == normalized_columns:
            return False
    existing_constraints = inspector.get_unique_constraints(table_name)
    for constraint in existing_constraints:
        if constraint.get("name") == index_name:
            return False
        if tuple(constraint.get("column_names") or []) == normalized_columns:
            return False

    unique_sql = "UNIQUE " if unique else ""
    columns_sql = ", ".join(columns)
    connection.execute(
        text(f"CREATE {unique_sql}INDEX {index_name} ON {table_name} ({columns_sql})")
    )
    return True
