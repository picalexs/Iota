"""
SQLAlchemy model for molecules.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.run import Run


class Molecule(Base):
    """
    Molecule model representing molecular systems.

    Each molecule can be used by multiple runs.
    """

    __tablename__ = "molecules"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_molecules_name_non_empty"),
        CheckConstraint("multiplicity >= 1", name="ck_molecules_multiplicity_ge_1"),
        UniqueConstraint("name", name="molecules_name_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    atoms: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
    )  # [{"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0}, ...]
    charge: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    multiplicity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active_space: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
    )  # {"n_electrons": 2, "n_orbitals": 2, ...}
    pubchem_cid: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    iupac_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    synonyms: Mapped[list | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
    )
    smiles: Mapped[str | None] = mapped_column(String(512), nullable=True)
    inchi: Mapped[str | None] = mapped_column(Text, nullable=True)
    inchi_key: Mapped[str | None] = mapped_column(String(27), nullable=True)

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

    # Relationships
    runs: Mapped[list[Run]] = relationship(
        "Run",
        back_populates="molecule",
        cascade="save-update, merge",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Molecule(id={self.id}, name={self.name})>"

    def to_chemistry_input(self, basis_set: str) -> dict[str, Any]:
        """Return the chemistry input consumed by the worker pipeline.

        The worker-side chemistry pipeline expects the backend molecule data in
        this shape:

        - ``atoms``: list of ``{symbol, x, y, z}`` dictionaries
        - ``basis``: run-level basis set supplied at execution time
        - ``charge``: molecular charge
        - ``multiplicity``: spin multiplicity
        - ``active_space``: copied through unchanged when present
        """
        chemistry_atoms = [
            {
                "symbol": str(atom["symbol"]),
                "x": float(atom["x"]),
                "y": float(atom["y"]),
                "z": float(atom["z"]),
            }
            for atom in self.atoms
        ]

        chemistry_input: dict[str, Any] = {
            "atoms": chemistry_atoms,
            "basis": basis_set,
            "charge": int(self.charge if self.charge is not None else 0),
            "multiplicity": int(self.multiplicity if self.multiplicity is not None else 1),
        }
        if self.active_space is not None:
            chemistry_input["active_space"] = dict(self.active_space)

        return chemistry_input
