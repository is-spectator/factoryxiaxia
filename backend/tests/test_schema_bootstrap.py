from pathlib import Path


def test_bootstrap_orders_schema_includes_activated_at():
    sql = Path(__file__).resolve().parents[1] / "init.sql"
    content = sql.read_text(encoding="utf-8")

    orders_section = content.split("CREATE TABLE IF NOT EXISTS orders (", 1)[1].split(") ENGINE=InnoDB", 1)[0]

    assert "activated_at DATETIME DEFAULT NULL" in orders_section
