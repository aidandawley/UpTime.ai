from sqlmodel import SQLModel, Session, create_engine
from app.config import settings

engine = create_engine(settings.database_url, echo=True)


def init_db():
    SQLModel.metadata.create_all(engine)
    _ensure_lightweight_migrations()


def get_session():
    with Session(engine) as session:
        yield session


def _ensure_lightweight_migrations():
    with engine.begin() as connection:
        table_info = connection.exec_driver_sql("PRAGMA table_info(recommendation)").fetchall()

        if not table_info:
            return

        columns = {row[1] for row in table_info}

        if "workflow_notes" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE recommendation ADD COLUMN workflow_notes VARCHAR NOT NULL DEFAULT ''"
            )

        additions = {
            "pr_url": "VARCHAR",
            "pr_number": "INTEGER",
            "pr_branch": "VARCHAR",
            "pr_creation_status": "VARCHAR NOT NULL DEFAULT 'not_requested'",
            "pr_creation_error": "VARCHAR",
        }
        for name, definition in additions.items():
            if name not in columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE recommendation ADD COLUMN {name} {definition}"
                )
