"""Molecule CRUD endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dependencies import ensure_local_operator_access, get_db, get_redis
from app.models import Run
from app.models.enums import BackendTarget
from app.schemas.molecule import (
    MoleculeCreate,
    MoleculeImportPreviewResponse,
    MoleculeListParams,
    MoleculeListResponse,
    MoleculeResponse,
    MoleculeSummaryListResponse,
    MoleculeSummaryResponse,
    MoleculeUpdate,
    PubChemImportRequest,
    PubChemSearchResponse,
    PubChemSearchResult,
    XYZImportRequest,
    XYZPreviewRequest,
    validate_molecule_response,
)
from app.services.molecule import MoleculeService
from app.services.pubchem_sync import search_pubchem_compounds

router = APIRouter()


def _list_molecules_for_request(
    db: Session,
    params: MoleculeListParams,
) -> MoleculeListResponse:
    service = MoleculeService(db)
    result = service.list_all(
        q=params.q,
        charge=params.charge,
        limit=params.limit,
        offset=params.offset,
    )
    return MoleculeListResponse(
        items=[validate_molecule_response(m) for m in result["items"]],
        total=result["total"],
    )


def _list_molecule_summaries_for_request(
    db: Session,
    params: MoleculeListParams,
) -> MoleculeSummaryListResponse:
    service = MoleculeService(db)
    result = service.list_all(
        q=params.q,
        charge=params.charge,
        limit=params.limit,
        offset=params.offset,
    )
    molecule_ids = [molecule.id for molecule in result["items"]]
    run_counts = {}
    if molecule_ids:
        run_counts = {
            molecule_id: int(count)
            for molecule_id, count in db.execute(
                select(Run.molecule_id, func.count(Run.id))
                .where(Run.molecule_id.in_(molecule_ids))
                .group_by(Run.molecule_id)
            ).all()
        }
    return MoleculeSummaryListResponse(
        items=[
            MoleculeSummaryResponse.from_molecule(
                molecule,
                run_count=run_counts.get(molecule.id, 0),
            )
            for molecule in result["items"]
        ],
        total=result["total"],
    )


def _get_molecule_for_request(
    db: Session,
    molecule_id: UUID,
) -> MoleculeResponse:
    service = MoleculeService(db)
    molecule = service.get_by_id(molecule_id)
    return validate_molecule_response(molecule)


@router.get("/pubchem/search")
async def search_pubchem(
    q: Annotated[str, Query(min_length=1, max_length=200)],
) -> PubChemSearchResponse:
    """
    Search PubChem for compounds matching the query string.
    Handles typos via PubChem autocomplete.
    Does NOT import anything — just returns candidates.
    """
    results = await search_pubchem_compounds(q)
    return PubChemSearchResponse(results=[PubChemSearchResult(**r) for r in results])


@router.post(
    "/pubchem/preview",
)
async def preview_molecule_from_pubchem(
    data: PubChemImportRequest,
    db: Annotated[Session, Depends(get_db)],
) -> MoleculeImportPreviewResponse:
    """Fetch PubChem geometry and metadata without storing the molecule."""
    service = MoleculeService(db)
    return await service.preview_pubchem_import(data)


@router.post(
    "/pubchem/import",
    response_model=MoleculeResponse,
    responses={
        200: {"model": MoleculeResponse, "description": "Molecule already existed"},
        201: {"model": MoleculeResponse, "description": "Molecule created from PubChem"},
    },
)
async def import_molecule_from_pubchem(
    data: PubChemImportRequest,
    db: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    """
    Fetch a single molecule by name from PubChem and store it.

    Raises:
        404: If PubChem has no 3-D record for the name.
        409: If a molecule with that name already exists.
    """
    service = MoleculeService(db)
    molecule, created = await service.import_from_pubchem(data.name, data.display_name)
    status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return JSONResponse(
        status_code=status_code,
        content=validate_molecule_response(molecule).model_dump(mode="json"),
    )


@router.post(
    "/xyz/preview",
)
def preview_molecule_from_xyz(
    data: XYZPreviewRequest,
    db: Annotated[Session, Depends(get_db)],
) -> MoleculeImportPreviewResponse:
    """Parse an XYZ geometry and return a non-persisted preview."""
    service = MoleculeService(db)
    return service.preview_xyz_import(data)


@router.post(
    "/xyz/import",
    status_code=status.HTTP_201_CREATED,
)
def import_molecule_from_xyz(
    data: XYZImportRequest,
    db: Annotated[Session, Depends(get_db)],
) -> MoleculeResponse:
    """Parse and store a molecule from standard XYZ coordinates."""
    service = MoleculeService(db)
    molecule = service.import_from_xyz(data)
    return validate_molecule_response(molecule)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_molecule(
    molecule_in: MoleculeCreate,
    db: Annotated[Session, Depends(get_db)],
) -> MoleculeResponse:
    """
    Create a new molecule.

    Validates atomic structure and ensures name uniqueness.
    """
    service = MoleculeService(db)
    molecule = service.create(molecule_in)
    return validate_molecule_response(molecule)


@router.get("")
def list_molecules(
    params: Annotated[MoleculeListParams, Query()],
    db: Annotated[Session, Depends(get_db)],
) -> MoleculeListResponse:
    """
    List molecules with optional search, filter, and pagination.

    Query parameters:
    - **q**: Case-insensitive substring search on name.
    - **charge**: Exact filter on charge.
    - **limit**: Page size (1–200, default 50).
    - **offset**: Page offset (default 0).
    """
    return _list_molecules_for_request(db, params)


@router.get("/summaries")
def list_molecule_summaries(
    params: Annotated[MoleculeListParams, Query()],
    db: Annotated[Session, Depends(get_db)],
) -> MoleculeSummaryListResponse:
    """
    List lightweight molecule summaries for high-volume library views.

    Query parameters mirror ``GET /api/molecules`` but return compact items with
    precomputed ``formula`` and ``atom_count`` instead of full coordinates.
    """
    return _list_molecule_summaries_for_request(db, params)


@router.get("/{molecule_id}")
def get_molecule(
    molecule_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> MoleculeResponse:
    """
    Get a specific molecule by ID.

    Raises:
        404: If molecule not found
    """
    return _get_molecule_for_request(db, molecule_id)


@router.patch("/{molecule_id}")
def update_molecule(
    molecule_id: UUID,
    molecule_in: MoleculeUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> MoleculeResponse:
    """
    Update a molecule.

    Allows partial updates of molecule definition fields.

    Raises:
        404: If molecule not found
        409: If name conflicts with another molecule
    """
    service = MoleculeService(db)
    molecule = service.update(molecule_id, molecule_in)
    return validate_molecule_response(molecule)


@router.delete("/{molecule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_molecule(
    molecule_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis)],
    http_request: Request,
    delete_associated_runs: Annotated[
        bool,
        Query(
            description="Also delete any persisted runs that reference the molecule.",
        ),
    ] = False,
) -> None:
    """
    Delete a molecule.

    Fails if the molecule has associated runs unless they are explicitly deleted
    in the same request.

    Raises:
        404: If molecule not found
        409: If molecule has runs
    """
    service = MoleculeService(db)
    if delete_associated_runs:
        associated_runs = service.list_associated_runs(molecule_id)
        if any(
            run.backend_target == BackendTarget.IBM_RUNTIME
            or run.credential_profile_id is not None
            or run.ibm_job_id is not None
            for run in associated_runs
        ):
            ensure_local_operator_access(http_request)
    service.delete(
        molecule_id,
        delete_associated_runs=delete_associated_runs,
        redis_client=redis,
    )
