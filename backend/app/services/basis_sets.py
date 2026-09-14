"""Central basis-set registry used by API validation and frontend selectors."""

from __future__ import annotations

from app.schemas.basis import BasisSetListResponse, BasisSetMetadata

SUPPORTED_BASIS_SETS: tuple[BasisSetMetadata, ...] = (
    BasisSetMetadata(
        id="sto-3g",
        label="STO-3G",
        description="Minimal basis; fastest and suitable for exploratory runs.",
        family="minimal",
        recommended=True,
        supported_elements=["H", "He", "Li", "Be", "B", "C", "N", "O", "F"],
    ),
    BasisSetMetadata(
        id="3-21g",
        label="3-21G",
        description="Split-valence basis with moderate cost.",
        family="pople",
        supported_elements=[
            "H",
            "Li",
            "Be",
            "B",
            "C",
            "N",
            "O",
            "F",
            "Na",
            "Mg",
            "Al",
            "Si",
            "P",
            "S",
            "Cl",
        ],
    ),
    BasisSetMetadata(
        id="6-31g",
        label="6-31G",
        description="Common split-valence Pople basis for small molecules.",
        family="pople",
        supported_elements=["H", "B", "C", "N", "O", "F", "P", "S", "Cl"],
    ),
    BasisSetMetadata(
        id="6-31g*",
        label="6-31G*",
        description="6-31G with polarization functions.",
        family="pople",
        supported_elements=["H", "B", "C", "N", "O", "F", "P", "S", "Cl"],
    ),
    BasisSetMetadata(
        id="cc-pvdz",
        label="cc-pVDZ",
        description="Correlation-consistent double-zeta basis.",
        family="correlation-consistent",
        supported_elements=["H", "He", "B", "C", "N", "O", "F"],
    ),
    BasisSetMetadata(
        id="cc-pvtz",
        label="cc-pVTZ",
        description="Correlation-consistent triple-zeta basis; higher cost.",
        family="correlation-consistent",
        supported_elements=["H", "He", "B", "C", "N", "O", "F"],
    ),
    BasisSetMetadata(
        id="def2-svp",
        label="def2-SVP",
        description="Ahlrichs split-valence polarized basis.",
        family="def2",
        supported_elements=[],
    ),
    BasisSetMetadata(
        id="def2-tzvp",
        label="def2-TZVP",
        description="Ahlrichs triple-zeta valence polarized basis.",
        family="def2",
        supported_elements=[],
    ),
)

SUPPORTED_BASIS_SET_IDS = frozenset(item.id for item in SUPPORTED_BASIS_SETS)
DEFAULT_BASIS_SET = "sto-3g"


def list_basis_sets() -> BasisSetListResponse:
    """Return selectable basis metadata."""
    return BasisSetListResponse(
        default_basis_set=DEFAULT_BASIS_SET,
        basis_sets=[item.model_copy(deep=True) for item in SUPPORTED_BASIS_SETS],
    )


def normalize_basis_set(value: str | None) -> str:
    """Normalize and validate a basis-set ID."""
    candidate = (value or DEFAULT_BASIS_SET).strip().lower()
    if candidate not in SUPPORTED_BASIS_SET_IDS:
        allowed = ", ".join(sorted(SUPPORTED_BASIS_SET_IDS))
        raise ValueError(f"Unsupported basis set '{value}'. Choose one of: {allowed}.")
    return candidate
