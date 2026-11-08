from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_initial_migration_upgrade_and_downgrade(tmp_path):
    database_path = tmp_path / "migration-test.db"
    engine = create_engine(f"sqlite:///{database_path}")
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["connection"] = engine.connect()

    try:
        command.upgrade(config, "head")
        inspector = inspect(config.attributes["connection"])

        assert "users" in inspector.get_table_names()
        assert "alembic_version" in inspector.get_table_names()
        columns = {column["name"] for column in inspector.get_columns("users")}
        assert columns == {
            "id",
            "email",
            "full_name",
            "password_hash",
            "role",
            "is_active",
            "created_at",
        }

        command.downgrade(config, "base")
        assert "users" not in inspect(config.attributes["connection"]).get_table_names()
    finally:
        config.attributes["connection"].close()
        engine.dispose()
