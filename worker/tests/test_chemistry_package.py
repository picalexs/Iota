"""Tests for the chemistry package import boundary."""

from __future__ import annotations

import os
import subprocess
import sys


def test_importing_chemistry_package_does_not_load_solver_modules() -> None:
    source = """
import sys
import worker.chemistry
assert not any(
    name.rsplit('.', 1)[-1].endswith('_solver')
    for name in sys.modules
    if name.startswith('worker.chemistry.')
)
"""
    environment = {**os.environ, "PYTHONPATH": os.getcwd()}

    completed = subprocess.run(
        [sys.executable, "-c", source],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
