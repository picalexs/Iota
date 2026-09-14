"""
PubChem synchronization orchestration.

Main sync function that coordinates fetching molecules from PubChem and
upserting them into the local database.
"""

from __future__ import annotations

import logging
from typing import TypedDict, cast

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Molecule
from app.services.active_space import (
    derive_active_space_from_atoms,
    should_refresh_derived_active_space,
)
from app.services.pubchem_sync._curated_data import CURATED_MOLECULES, CompoundData, SyncResult
from app.services.pubchem_sync._fetchers import _fetch_full_compound_data

logger = logging.getLogger(__name__)


class _CuratedMolecule(TypedDict):
    name: str
    pubchem_name: str
    charge: int
    multiplicity: int


def _should_refresh_active_space(active_space: object) -> bool:
    """Return whether a stored active-space payload came from legacy seed data."""
    return should_refresh_derived_active_space(active_space)


def _is_default_seed_compatible(
    *,
    multiplicity: int,
    active_space: object,
) -> tuple[bool, str | None]:
    """Return whether a default-seeded molecule is selectable in the current rollout."""
    if multiplicity != 1:
        return False, "only singlet molecules are selectable in the current rollout"

    if not isinstance(active_space, dict):
        return False, "no bounded active space could be derived"

    n_electrons = active_space.get("n_electrons")
    n_orbitals = active_space.get("n_orbitals")
    if not isinstance(n_electrons, int) or not isinstance(n_orbitals, int):
        return False, "active-space electron and orbital counts are missing"
    if n_electrons <= 0 or n_orbitals <= 0:
        return False, "active-space electron and orbital counts must be positive"
    if n_electrons % 2 != 0:
        return False, "odd active-space electron counts are not selectable"
    if n_electrons > 2 * n_orbitals:
        return False, "active-space electrons exceed twice the active orbitals"
    return True, None


def _select_molecules_to_sync(molecule_names: list[str] | None) -> list[_CuratedMolecule]:
    molecules = cast(list[_CuratedMolecule], CURATED_MOLECULES)
    if molecule_names:
        return [molecule for molecule in molecules if molecule["name"] in molecule_names]
    return molecules


def _lookup_existing_by_name(db: Session, name: str) -> Molecule | None:
    return db.scalars(select(Molecule).where(func.lower(Molecule.name) == name.lower())).first()


def _lookup_existing_by_cid(db: Session, cid: int) -> Molecule | None:
    return db.scalars(select(Molecule).where(Molecule.pubchem_cid == cid)).first()


def _commit_active_space_refresh(
    db: Session,
    *,
    molecule: Molecule,
    molecule_name: str,
) -> None:
    active_space = derive_active_space_from_atoms(
        molecule.atoms,
        charge=molecule.charge,
        multiplicity=molecule.multiplicity,
    )
    if active_space is None:
        return

    molecule.active_space = active_space
    try:
        db.commit()
        logger.info("Stored derived active_space for molecule '%s'.", molecule_name)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning("Failed to store active_space for '%s': %s", molecule_name, exc)


def _refresh_existing_active_space_if_needed(
    db: Session,
    *,
    molecule: Molecule,
    molecule_name: str,
    log_skip_when_fresh: bool,
) -> None:
    if _should_refresh_active_space(molecule.active_space):
        _commit_active_space_refresh(
            db,
            molecule=molecule,
            molecule_name=molecule_name,
        )
        return

    if log_skip_when_fresh:
        logger.debug("Molecule '%s' already exists — skipping.", molecule_name)


def _handle_existing_molecule(
    db: Session,
    *,
    existing: Molecule | None,
    molecule_name: str,
    result: SyncResult,
) -> bool:
    if existing is None:
        return False

    _refresh_existing_active_space_if_needed(
        db,
        molecule=existing,
        molecule_name=molecule_name,
        log_skip_when_fresh=True,
    )
    result.skipped += 1
    return True


def _handle_existing_cid_molecule(
    db: Session,
    *,
    existing: Molecule | None,
    requested_name: str,
    cid: int,
    result: SyncResult,
) -> bool:
    if existing is None:
        return False

    logger.info(
        "Skipping molecule '%s': PubChem CID %s already exists as '%s'.",
        requested_name,
        cid,
        existing.name,
    )
    _refresh_existing_active_space_if_needed(
        db,
        molecule=existing,
        molecule_name=existing.name,
        log_skip_when_fresh=False,
    )
    result.skipped += 1
    return True


def _should_skip_default_seed_for_multiplicity(
    *,
    is_default_seed: bool,
    molecule_name: str,
    multiplicity: int,
    result: SyncResult,
) -> bool:
    if not is_default_seed or multiplicity == 1:
        return False

    logger.info(
        "Skipping default molecule '%s': multiplicity=%s is not selectable.",
        molecule_name,
        multiplicity,
    )
    result.skipped += 1
    return True


def _should_skip_default_seed_for_active_space(
    *,
    is_default_seed: bool,
    molecule_name: str,
    multiplicity: int,
    active_space: object,
    result: SyncResult,
) -> bool:
    if not is_default_seed:
        return False

    compatible, reason = _is_default_seed_compatible(
        multiplicity=multiplicity,
        active_space=active_space,
    )
    if compatible:
        return False

    logger.info("Skipping default molecule '%s': %s.", molecule_name, reason)
    result.skipped += 1
    return True


def _build_pubchem_molecule(
    *,
    molecule_name: str,
    charge: int,
    multiplicity: int,
    active_space: object,
    compound_data: CompoundData,
) -> Molecule:
    return Molecule(
        name=molecule_name,
        atoms=compound_data.atoms,
        charge=charge,
        multiplicity=multiplicity,
        active_space=active_space,
        pubchem_cid=compound_data.cid,
        iupac_name=compound_data.iupac_name,
        description=compound_data.description,
        synonyms=compound_data.synonyms,
        smiles=compound_data.smiles,
        inchi=compound_data.inchi,
        inchi_key=compound_data.inchi_key,
    )


def _insert_molecule(
    db: Session,
    *,
    molecule: Molecule,
    molecule_name: str,
    result: SyncResult,
) -> None:
    db.add(molecule)
    try:
        db.commit()
        db.refresh(molecule)
        result.added += 1
        logger.info("Added molecule '%s' from PubChem.", molecule_name)
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Failed to insert molecule '%s'.", molecule_name)
        result.failed.append(molecule_name)


async def _sync_single_molecule(
    db: Session,
    *,
    client: httpx.AsyncClient,
    mol_info: _CuratedMolecule,
    is_default_seed: bool,
    result: SyncResult,
) -> None:
    name = str(mol_info["name"])
    pubchem_name = str(mol_info["pubchem_name"])
    multiplicity = mol_info["multiplicity"]

    if _handle_existing_molecule(
        db,
        existing=_lookup_existing_by_name(db, name),
        molecule_name=name,
        result=result,
    ):
        return

    compound_data = await _fetch_full_compound_data(client, pubchem_name)
    if compound_data is None:
        logger.info(
            "Could not fetch geometry for '%s' (%s) — skipping.",
            name,
            pubchem_name,
        )
        result.failed.append(name)
        return

    if _handle_existing_cid_molecule(
        db,
        existing=_lookup_existing_by_cid(db, compound_data.cid),
        requested_name=name,
        cid=compound_data.cid,
        result=result,
    ):
        return

    active_space = derive_active_space_from_atoms(
        compound_data.atoms,
        charge=mol_info["charge"],
        multiplicity=multiplicity,
    )
    if _should_skip_default_seed_for_active_space(
        is_default_seed=is_default_seed,
        molecule_name=name,
        multiplicity=multiplicity,
        active_space=active_space,
        result=result,
    ):
        return

    molecule = _build_pubchem_molecule(
        molecule_name=name,
        charge=mol_info["charge"],
        multiplicity=multiplicity,
        active_space=active_space,
        compound_data=compound_data,
    )
    _insert_molecule(
        db,
        molecule=molecule,
        molecule_name=name,
        result=result,
    )


async def sync_from_pubchem(
    db: Session,
    molecule_names: list[str] | None = None,
) -> SyncResult:
    """
    Synchronise curated molecules from PubChem into *db*.

    Existing molecules (matched by ``name``) are left untouched.  Only new
    molecules are inserted.

    Args:
        db: Synchronous SQLAlchemy session.
        molecule_names: Optional allow-list of display names (e.g. ``["H2",
            "NH3"]``).  When *None*, all :data:`CURATED_MOLECULES` are synced.

    Returns:
        :class:`SyncResult` with counts of added, skipped, and failed molecules.
    """
    result = SyncResult()
    is_default_seed = molecule_names is None

    to_sync = _select_molecules_to_sync(molecule_names)

    async with httpx.AsyncClient() as client:
        for mol_info in to_sync:
            name = str(mol_info["name"])
            multiplicity = mol_info["multiplicity"]

            if _should_skip_default_seed_for_multiplicity(
                is_default_seed=is_default_seed,
                molecule_name=name,
                multiplicity=multiplicity,
                result=result,
            ):
                continue

            try:
                await _sync_single_molecule(
                    db,
                    client=client,
                    mol_info=mol_info,
                    is_default_seed=is_default_seed,
                    result=result,
                )
            except Exception:  # noqa: BLE001
                logger.exception("Unexpected error processing molecule '%s'.", name)
                result.failed.append(name)

    return result
