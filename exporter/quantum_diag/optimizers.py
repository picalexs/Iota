"""Optimizer configuration and getter."""

from __future__ import annotations

import warnings

from qiskit_algorithms.optimizers import COBYLA, SLSQP, SPSA


def get_optimizer(optimizer_name: str, **kwargs):
    """Get optimizer instance by name.

    Args:
        optimizer_name: Name of optimizer ('COBYLA', 'SLSQP', 'SPSA').
                **kwargs: Additional keyword arguments for the optimizer.
                        Special optional key:
                        - num_vars: Number of optimization variables. If provided with
                            COBYLA, validates SciPy's MAXFUN lower bound (num_vars + 2).

    Returns:
        Optimizer instance with specified configuration.

    Raises:
        ValueError: If optimizer_name is not recognized.
    """
    if optimizer_name == 'COBYLA':
        num_vars = kwargs.pop('num_vars', None)
        maxiter = kwargs.get('maxiter')
        if (
            isinstance(num_vars, int)
            and isinstance(maxiter, int)
            and maxiter < (num_vars + 2)
        ):
            warnings.warn(
                "COBYLA maxiter is lower than SciPy minimum MAXFUN "
                f"(maxiter={maxiter}, required>={num_vars + 2}). "
                "SciPy will auto-adjust this at runtime, which can impact "
                "cross-run comparability.",
                UserWarning,
            )
        return COBYLA(**kwargs)
    elif optimizer_name == 'SLSQP':
        return SLSQP(**kwargs)
    elif optimizer_name == 'SPSA':
        # Set sensible defaults for SPSA
        if 'maxiter' not in kwargs:
            kwargs['maxiter'] = 100
        if 'learning_rate' not in kwargs:
            kwargs['learning_rate'] = 0.1
        if 'perturbation' not in kwargs:
            kwargs['perturbation'] = 0.1
        return SPSA(**kwargs)
    else:
        raise ValueError(
            f"Unknown optimizer '{optimizer_name}'. "
            f"Valid options: 'COBYLA', 'SLSQP', 'SPSA'"
        )
