from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command

ROOT = Path(__file__).resolve().parents[1]


def test_migrations_upgrade_and_downgrade(tmp_path):
    database_path = tmp_path / "migration-test.db"
    engine = create_engine(f"sqlite:///{database_path}")
    connection = engine.connect()
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["connection"] = connection

    try:
        command.upgrade(config, "head")
        inspector = inspect(connection)
        expected_tables = {
            "users",
            "buyer_requirements",
            "produce_listings",
            "workflow_runs",
            "agent_tasks",
            "match_candidates",
            "alembic_version",
        }
        assert expected_tables.issubset(set(inspector.get_table_names()))

        user_columns = {column["name"] for column in inspector.get_columns("users")}
        assert user_columns == {
            "id",
            "email",
            "full_name",
            "password_hash",
            "role",
            "is_active",
            "created_at",
        }

        command.downgrade(config, "base")
        assert "users" not in inspect(connection).get_table_names()
    finally:
        connection.close()
        engine.dispose()
