from sqlalchemy import inspect, text

from migration_manager import apply_migrations, describe_migration_state, validate_migration_state


def test_apply_migrations_creates_schema_and_records_versions(app_module, db):
    with app_module.app.app_context():
        db.session.remove()
        db.drop_all()
        db.session.execute(text("DROP TABLE IF EXISTS schema_migrations"))
        db.session.commit()

        applied = apply_migrations(app_module)
        state = describe_migration_state(app_module)
        inspector = inspect(db.engine)

        assert [item["version"] for item in applied] == ["0001", "0002", "0003"]
        assert "users" in inspector.get_table_names()
        assert "deployments" in inspector.get_table_names()
        assert "kongkong_instances" in inspector.get_table_names()
        assert "schema_migrations" in inspector.get_table_names()
        assert state["pending"] == []


def test_validate_migration_state_rejects_pending_migrations(app_module, db):
    with app_module.app.app_context():
        db.session.remove()
        db.drop_all()
        db.session.execute(text("DROP TABLE IF EXISTS schema_migrations"))
        db.session.commit()

        try:
            validate_migration_state(app_module, app_env="production", env_map={})
        except RuntimeError as exc:
            assert "python manage.py migrate" in str(exc)
        else:
            raise AssertionError("expected pending migrations to be rejected")
