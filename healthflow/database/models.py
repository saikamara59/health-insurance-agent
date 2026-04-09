import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, TypeDecorator


class Base(DeclarativeBase):
    pass


class GUID(TypeDecorator):
    """Platform-independent UUID type.
    Uses PostgreSQL's UUID type when available, otherwise stores as String(36).
    """
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if isinstance(value, uuid.UUID):
                return str(value)
            return str(uuid.UUID(value))
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value) if not isinstance(value, uuid.UUID) else value
        return value


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Broker(Base):
    __tablename__ = "brokers"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="broker", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    clients: Mapped[list["Client"]] = relationship(back_populates="broker", cascade="all, delete-orphan")
    actions: Mapped[list["ActionHistory"]] = relationship(back_populates="broker", cascade="all, delete-orphan")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("brokers.id"), index=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(5), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    income_level: Mapped[str] = mapped_column(String(10), nullable=False)
    doctors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    prescriptions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    procedures: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    broker: Mapped["Broker"] = relationship(back_populates="clients")
    actions: Mapped[list["ActionHistory"]] = relationship(back_populates="client", cascade="all, delete-orphan")


class ActionHistory(Base):
    __tablename__ = "action_history"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("brokers.id"), index=True, nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("clients.id"), index=True, nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    request_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    response_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    broker: Mapped["Broker"] = relationship(back_populates="actions")
    client: Mapped["Client"] = relationship(back_populates="actions")
