"""Stable identifiers shared by API, worker, and persistence adapters."""

from enum import StrEnum


class RunStatus(StrEnum):
    """Valid lifecycle states for a run."""

    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSING = "PAUSING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXCLUDED = "EXCLUDED"
    SUBMITTED_TO_IBM = "SUBMITTED_TO_IBM"


class RunAlgorithm(StrEnum):
    """Supported production algorithms."""

    VQE = "vqe"
    QSE = "qse"
    KQD = "kqd"
    QFD = "qfd"
    SQD = "sqd"
    SKQD = "skqd"


class RunMode(StrEnum):
    """User-facing run mode."""

    EASY = "easy"
    ADVANCED = "advanced"


class EasyGoal(StrEnum):
    """Goal tiers for easy-mode expansion."""

    FASTEST = "fastest"
    BALANCED = "balanced"
    BEST_ACCURACY = "best_accuracy"


class BackendTarget(StrEnum):
    """Execution backends exposed by the API contract."""

    STATEVECTOR = "statevector"
    AER_SIMULATOR = "aer_simulator"
    IBM_RUNTIME = "ibm_runtime"


class RunEventType(StrEnum):
    """Event categories emitted during a run lifecycle."""

    STATUS_CHANGED = "status_changed"
    ITERATION_UPDATE = "iteration_update"
    ERROR = "error"
    RESULT = "result"
    ESTIMATE_UPDATED = "estimate_updated"
    IBM_JOB_SUBMITTED = "ibm_job_submitted"
    IBM_STATUS_POLL = "ibm_status_poll"
    CONTROL_REQUESTED = "control_requested"
    CHECKPOINT_SAVED = "checkpoint_saved"
    RESUME_ENQUEUED = "resume_enqueued"
    RESTART_CREATED = "restart_created"
