import uuid

from sqlalchemy import Column, ForeignKey, create_engine, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def uuid_pk() -> Column:
    """A UUID primary key column.

    The value is generated client-side (`uuid4`) so it is available immediately
    after `flush()` without a round-trip, and `gen_random_uuid()` is set as the
    server default so rows inserted via raw SQL get a UUID too.
    """
    return Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


def uuid_fk(
    target: str,
    *,
    nullable: bool = False,
    index: bool = False,
    ondelete: str | None = None,
    primary_key: bool = False,
) -> Column:
    """A UUID foreign-key column pointing at `target` (e.g. ``"users.id"``)."""
    return Column(
        UUID(as_uuid=True),
        ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
        index=index,
        primary_key=primary_key,
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()