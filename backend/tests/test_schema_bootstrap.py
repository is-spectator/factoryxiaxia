from pathlib import Path


def test_bootstrap_orders_schema_includes_activated_at():
    sql = Path(__file__).resolve().parents[1] / "init.sql"
    content = sql.read_text(encoding="utf-8")

    orders_section = content.split("CREATE TABLE IF NOT EXISTS orders (", 1)[1].split(") ENGINE=InnoDB", 1)[0]

    assert "activated_at DATETIME DEFAULT NULL" in orders_section


def test_bootstrap_workers_schema_includes_agent_fields():
    sql = Path(__file__).resolve().parents[1] / "init.sql"
    content = sql.read_text(encoding="utf-8")

    workers_section = content.split("CREATE TABLE IF NOT EXISTS workers (", 1)[1].split(") ENGINE=InnoDB", 1)[0]

    assert "worker_type VARCHAR(30) DEFAULT 'general'" in workers_section
    assert "delivery_mode VARCHAR(30) DEFAULT 'manual_service'" in workers_section
    assert "template_key VARCHAR(80) DEFAULT NULL" in workers_section


def test_bootstrap_deployments_schema_includes_public_token():
    sql = Path(__file__).resolve().parents[1] / "init.sql"
    content = sql.read_text(encoding="utf-8")

    deployments_section = content.split("CREATE TABLE IF NOT EXISTS deployments (", 1)[1].split(") ENGINE=InnoDB", 1)[0]

    assert "public_token VARCHAR(120) DEFAULT NULL UNIQUE" in deployments_section


def test_bootstrap_contains_agent_tables():
    sql = Path(__file__).resolve().parents[1] / "init.sql"
    content = sql.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS organizations (" in content
    assert "CREATE TABLE IF NOT EXISTS agent_templates (" in content
    assert "CREATE TABLE IF NOT EXISTS service_plans (" in content
    assert "CREATE TABLE IF NOT EXISTS deployments (" in content
    assert "CREATE TABLE IF NOT EXISTS knowledge_bases (" in content
    assert "CREATE TABLE IF NOT EXISTS knowledge_documents (" in content
    assert "CREATE TABLE IF NOT EXISTS conversation_sessions (" in content
    assert "CREATE TABLE IF NOT EXISTS conversation_messages (" in content
    assert "CREATE TABLE IF NOT EXISTS handoff_tickets (" in content
    assert "CREATE TABLE IF NOT EXISTS usage_records (" in content
    assert "CREATE TABLE IF NOT EXISTS audit_logs (" in content
