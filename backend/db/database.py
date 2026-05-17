from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import text
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./finance.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Crée toutes les tables si elles n'existent pas."""
    from db.models import Base as ModelsBase  # noqa: F401
    ModelsBase.metadata.create_all(bind=engine)
    _run_lightweight_migrations()


def _run_lightweight_migrations():
    """Petites migrations SQLite idempotentes pour l'app locale."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.connect() as conn:
        group_cols = [
            row[1]
            for row in conn.execute(text("PRAGMA table_info(category_groups)"))
        ]
        added_projection_mode = "projection_mode" not in group_cols
        if added_projection_mode:
            conn.execute(text(
                "ALTER TABLE category_groups "
                "ADD COLUMN projection_mode VARCHAR(32) NOT NULL DEFAULT 'linear'"
            ))

            fixed = ("Logement", "Abonnements", "Banque & Assurance", "Impôts")
            actual = ("Vacances", "Maison & Équipement", "Loisirs & Sorties", "Autre")
            for name in fixed:
                conn.execute(
                    text("UPDATE category_groups SET projection_mode = 'fixed_historical' WHERE name = :name"),
                    {"name": name},
                )
            for name in actual:
                conn.execute(
                    text("UPDATE category_groups SET projection_mode = 'actual_only' WHERE name = :name"),
                    {"name": name},
                )
            conn.execute(text(
                "UPDATE category_groups SET projection_mode = 'linear' "
                "WHERE projection_mode IS NULL OR projection_mode = ''"
            ))
        conn.commit()
