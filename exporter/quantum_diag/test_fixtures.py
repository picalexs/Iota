"""Test molecule fixtures and geometry setup."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


GEOMETRY_PROVENANCE: dict[str, dict[str, str]] = {
    "H2": {
        "reference": "NIST CCCBDB / spectroscopy consensus",
        "url": "https://cccbdb.nist.gov/expbondlengths2x.asp?all=0&descript=rHH",
        "accessed_utc": "2026-03-28",
        "note": "Equilibrium H-H bond length set to 0.7414 Angstrom.",
    },
    "LiH": {
        "reference": "NIST Diatomic Molecular Constants",
        "url": "https://physics.nist.gov/PhysRefData/MolSpec/Diatomic/Html/Tables/LiH.html",
        "accessed_utc": "2026-03-28",
        "note": "Equilibrium Li-H bond length set to 1.5949131 Angstrom.",
    },
    "H2O": {
        "reference": "NIST CCCBDB experimental geometry",
        "url": "https://cccbdb.nist.gov/listangleexp3x.asp?bi=9&descript=aHOH&mi=63",
        "accessed_utc": "2026-03-28",
        "note": "O-H = 0.95784 Angstrom, H-O-H = 104.5 degrees.",
    },
    "BeH2": {
        "reference": "NIST CCCBDB reference geometry table",
        "url": "https://cccbdb.nist.gov/expbondlengths2x.asp?descript=rBeH",
        "accessed_utc": "2026-03-28",
        "note": "Linear BeH2 with Be-H = 1.326 Angstrom.",
    },
    "NH3": {
        "reference": "NIST CCCBDB reference geometry table",
        "url": "https://cccbdb.nist.gov/listbondexp3x.asp?bi=8&descript=rNH&mi=61",
        "accessed_utc": "2026-03-28",
        "note": "N-H = 1.012 Angstrom, H-N-H = 106.7 degrees.",
    },
}


@dataclass
class MoleculeGeometry:
    """Molecular geometry specification.

    Attributes:
        symbols: List of element symbols (e.g., ["H", "H"]).
        xyz_coords: Cartesian coordinates as numpy array of shape (natoms, 3).
        active_space: Tuple of (n_electrons, n_orbitals) for active space, or None.
    """

    symbols: list[str]
    xyz_coords: np.ndarray
    active_space: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        """Validate geometry."""
        if len(self.symbols) != self.xyz_coords.shape[0]:
            raise ValueError(
                f"symbols length {len(self.symbols)} does not match "
                f"xyz_coords shape {self.xyz_coords.shape[0]}"
            )
        if self.xyz_coords.shape[1] != 3:
            raise ValueError(
                f"xyz_coords must have shape (natoms, 3), got {self.xyz_coords.shape}"
            )


def get_geometry_provenance(molecule_name: str) -> dict[str, str]:
    """Return provenance metadata for the molecule fixture defaults."""
    if molecule_name not in GEOMETRY_PROVENANCE:
        raise ValueError(
            f"Unknown molecule '{molecule_name}'. "
            f"Available entries: {sorted(GEOMETRY_PROVENANCE.keys())}"
        )
    return GEOMETRY_PROVENANCE[molecule_name].copy()


def get_h2_geometry(bond_length: float = 0.7414) -> MoleculeGeometry:
    """Get H2 molecule geometry.

    Args:
        bond_length: H-H bond length in Angstrom. Default 0.7414.

    Returns:
        MoleculeGeometry for H2 with active space (2, 2).
    """
    symbols = ["H", "H"]
    # Place atoms along z-axis, centered at origin
    half_length = bond_length / 2.0
    xyz_coords = np.array([
        [0.0, 0.0, -half_length],
        [0.0, 0.0, half_length],
    ])
    return MoleculeGeometry(
        symbols=symbols,
        xyz_coords=xyz_coords,
        active_space=(2, 2),  # 2 electrons, 2 orbitals
    )


def get_lih_geometry(bond_length: float = 1.5949131) -> MoleculeGeometry:
    """Get LiH molecule geometry.

    Args:
        bond_length: Li-H bond length in Angstrom. Default 1.5949131.

    Returns:
        MoleculeGeometry for LiH with active space (4, 4).
    """
    symbols = ["Li", "H"]
    # Place Li at origin, H along z-axis
    xyz_coords = np.array([
        [0.0, 0.0, 0.0],
        [0.0, 0.0, bond_length],
    ])
    return MoleculeGeometry(
        symbols=symbols,
        xyz_coords=xyz_coords,
        active_space=(4, 4),  # 4 electrons, 4 orbitals
    )


def get_h2o_geometry(
    oh_bond_length: float = 0.95784,
    hoh_angle: float = 104.5,
) -> MoleculeGeometry:
    """Get H2O (water) molecule geometry.

    Places O at origin with two H atoms symmetrically positioned to achieve
    the specified H-O-H angle. The geometry is placed in the xz-plane with
    both hydrogens at equal angles from the z-axis.

    Args:
        oh_bond_length: O-H bond length in Angstrom. Default 0.95784.
        hoh_angle: H-O-H angle in degrees. Default 104.5°.

    Returns:
        MoleculeGeometry for H2O with active space (10, 6).

    Example:
        With defaults (hoh_angle=104.5°), produces:
        - O at [0, 0, 0] (origin)
        - H1 at [0.95784*sin(52.25°), 0, 0.95784*cos(52.25°)]
        - H2 at [-0.95784*sin(52.25°), 0, 0.95784*cos(52.25°)]
        - Verified H-O-H angle = 104.5° via dot product
    """
    symbols = ["O", "H", "H"]
    # Place O at origin, both H atoms symmetrically in xz-plane
    # Each H is at half-angle from z-axis: hoh_angle / 2
    half_angle_rad = np.radians(hoh_angle / 2)

    # H1 at positive x displacement
    h1 = np.array([
        oh_bond_length * np.sin(half_angle_rad),
        0.0,
        oh_bond_length * np.cos(half_angle_rad),
    ])
    # H2 at negative x displacement (symmetric about z-axis)
    h2 = np.array([
        -oh_bond_length * np.sin(half_angle_rad),
        0.0,
        oh_bond_length * np.cos(half_angle_rad),
    ])
    xyz_coords = np.array([
        [0.0, 0.0, 0.0],  # O at origin
        h1,
        h2,
    ])
    return MoleculeGeometry(
        symbols=symbols,
        xyz_coords=xyz_coords,
        active_space=(10, 6),  # 10 electrons, 6 orbitals (STO-3G minimal basis)
    )


def get_beh2_geometry(beh_bond_length: float = 1.326) -> MoleculeGeometry:
    """Get BeH2 (beryllium dihydride) molecule geometry.

    Args:
        beh_bond_length: Be-H bond length in Angstrom. Default 1.326.

    Returns:
        MoleculeGeometry for BeH2 with active space (4, 4).
    """
    symbols = ["Be", "H", "H"]
    # Linear molecule: Be at origin, H's along z-axis
    xyz_coords = np.array([
        [0.0, 0.0, 0.0],  # Be at origin
        [0.0, 0.0, -beh_bond_length],  # H1 along negative z
        [0.0, 0.0, beh_bond_length],   # H2 along positive z
    ])
    return MoleculeGeometry(
        symbols=symbols,
        xyz_coords=xyz_coords,
        active_space=(4, 4),  # 4 electrons, 4 orbitals (STO-3G minimal basis)
    )


def get_nh3_geometry(
    nh_bond_length: float = 1.012,
    hnh_angle: float = 106.7,
) -> MoleculeGeometry:
    """Get NH3 (ammonia) geometry in a trigonal-pyramidal arrangement.

    Returns:
        MoleculeGeometry for NH3 with active space (8, 7).
    """
    symbols = ["N", "H", "H", "H"]
    # For three equivalent N-H bonds with 120° azimuthal separation,
    # cos(angle_HNH) = 1.5 * cos(theta)^2 - 0.5, where theta is the
    # polar angle from +z for each bond vector.
    cos_hnh = float(np.cos(np.radians(hnh_angle)))
    cos_theta_sq = (cos_hnh + 0.5) / 1.5
    cos_theta_sq = float(np.clip(cos_theta_sq, 0.0, 1.0))
    cos_theta = float(np.sqrt(cos_theta_sq))
    sin_theta = float(np.sqrt(max(0.0, 1.0 - cos_theta_sq)))

    # Place hydrogens in a plane below N for a standard pyramid orientation.
    z_h = -nh_bond_length * cos_theta
    radial = nh_bond_length * sin_theta
    h1 = np.array([0.0, radial, z_h])
    h2 = np.array([radial * np.sqrt(3) / 2.0, -radial / 2.0, z_h])
    h3 = np.array([-radial * np.sqrt(3) / 2.0, -radial / 2.0, z_h])

    xyz_coords = np.array([
        [0.0, 0.0, 0.0],  # N at origin
        h1,
        h2,
        h3,
    ])
    return MoleculeGeometry(
        symbols=symbols,
        xyz_coords=xyz_coords,
        active_space=(8, 7),
    )
