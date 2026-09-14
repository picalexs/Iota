"""Encrypted local IBM Runtime credential profiles."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.run import Run


class IbmCredentialProfile(Base):
    """Locally stored IBM credential profile with encrypted secret fields."""

    __tablename__ = "ibm_credential_profiles"
    __table_args__ = (
        Index("idx_ibm_credential_profiles_active", "active"),
        Index("idx_ibm_credential_profiles_name", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    encrypted_token: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_crn: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(64), nullable=False, default="ibm_quantum_platform")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    token_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    crn_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    runs: Mapped[list[Run]] = relationship("Run", back_populates="credential_profile")

    def __repr__(self) -> str:
        return f"<IbmCredentialProfile(id={self.id}, name={self.name!r}, active={self.active})>"
