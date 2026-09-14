import {
  useState,
  useEffect,
  useRef,
  type Dispatch,
  type RefObject,
  type SetStateAction,
} from "react";
import { useLocation, useNavigate } from "@tanstack/react-router";
import { useSmartBack } from "@/hooks/use-smart-back";
import { ChevronLeft } from "lucide-react";
import { getMolecule } from "@/api/molecules";
import {
  getRun,
  cancelRun,
  pauseRun,
  resumeRun,
  restartRun,
  getRunResult,
  getRunEvents,
} from "@/api/runs";
import { logAppError } from "@/lib/app-logger";
import { getErrorMessage } from "@/lib/error-handler";
import { getRunActivityLabel, isRunExecuting } from "@/lib/run-status-display";
import type {
  RunResponse,
  MoleculeResponse,
  RunResultResponse,
  RunEventResponse,
  RunRestartResponse,
} from "@/types/run";
import { RunHeader } from "./run-detail/run-header";
import { useRunSseSubscription } from "./run-detail/use-run-sse-subscription";
import { ResultsDashboard } from "@/components/results/results-dashboard";
import { RunDetailLoadingSkeleton } from "./run-detail-loading";
import { PageErrorState, getErrorPresentation } from "@/components/ui/page-error-state";

const CANCELLABLE_STATUSES = new Set<RunResponse["status"]>([
  "CREATED",
  "RUNNING",
  "QUEUED",
  "PAUSING",
  "PAUSED",
  "SUBMITTED_TO_IBM",
]);
const PAUSABLE_STATUSES = new Set<RunResponse["status"]>([
  "CREATED",
  "RUNNING",
  "QUEUED",
  "SUBMITTED_TO_IBM",
]);
const RESTARTABLE_STATUSES = new Set<RunResponse["status"]>([
  "COMPLETED",
  "FAILED",
  "CANCELLED",
  "EXCLUDED",
  "PAUSED",
]);
const RESUMABLE_STATUSES = new Set<RunResponse["status"]>(["PAUSED", "FAILED"]);

type RunAction = "cancel" | "pause" | "resume" | "restart";

function isFullRunResponse(response: RunRestartResponse): response is RunResponse {
  return "molecule_id" in response && "config_json" in response;
}

function getRestartTargetId(response: RunRestartResponse): string {
  if ("child_run_id" in response && response.child_run_id) return response.child_run_id;
  if ("new_run_id" in response && response.new_run_id) return response.new_run_id;
  if ("target_run_id" in response && response.target_run_id) return response.target_run_id;
  return response.id;
}

export interface RunDetailProps {
  readonly runId: string;
}

interface BackgroundLoadContext {
  readonly isActive: () => boolean;
}

interface LoadRunEventsContext extends BackgroundLoadContext {
  readonly runId: string;
  readonly setEvents: Dispatch<SetStateAction<RunEventResponse[]>>;
  readonly setEventsPending: Dispatch<SetStateAction<boolean>>;
  readonly lastSequenceRef: RefObject<number>;
  readonly seenSequencesRef: RefObject<Set<number>>;
}

async function loadRunEvents({
  runId,
  isActive,
  setEvents,
  setEventsPending,
  lastSequenceRef,
  seenSequencesRef,
}: LoadRunEventsContext): Promise<void> {
  try {
    const eventsRes = await getRunEvents(runId);
    if (!isActive()) return;
    setEvents(eventsRes.events);
    lastSequenceRef.current = eventsRes.last_sequence;
    seenSequencesRef.current = new Set(eventsRes.events.map((event) => event.sequence));
  } catch (error) {
    logAppError("run-detail.events", "Failed to load run events.", error, { runId });
    if (isActive()) {
      setEvents([]);
    }
  } finally {
    if (isActive()) {
      setEventsPending(false);
    }
  }
}

async function loadRunMolecule(
  moleculeId: string,
  isActive: () => boolean,
  setMolecule: Dispatch<SetStateAction<MoleculeResponse | null>>,
  setMoleculePending: Dispatch<SetStateAction<boolean>>,
): Promise<void> {
  try {
    const moleculeRes = await getMolecule(moleculeId);
    if (isActive()) {
      setMolecule(moleculeRes);
    }
  } catch (error) {
    logAppError("run-detail.molecule", "Failed to load run molecule.", error, { moleculeId });
    if (isActive()) {
      setMolecule(null);
    }
  } finally {
    if (isActive()) {
      setMoleculePending(false);
    }
  }
}

async function loadRunResult(
  runId: string,
  isActive: () => boolean,
  setResult: Dispatch<SetStateAction<RunResultResponse | null>>,
  setResultPending: Dispatch<SetStateAction<boolean>>,
): Promise<void> {
  try {
    const fetchedResult = await getRunResult(runId);
    if (isActive()) {
      setResult(fetchedResult);
    }
  } catch (error) {
    logAppError("run-detail.result", "Failed to load run result.", error, { runId });
    if (isActive()) {
      setResult(null);
    }
  } finally {
    if (isActive()) {
      setResultPending(false);
    }
  }
}

export function RunDetail({ runId }: RunDetailProps) {
  const shouldGoToList = useLocation({
    select: (location) => {
      const state = location.state;
      if (!state || typeof state !== "object") {
        return false;
      }

      return "__source" in state && (state as Record<string, unknown>).__source === "run-create";
    },
  });
  const goBack = useSmartBack({ to: "/runs" }, { forceFallback: shouldGoToList });
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<Error | null>(null);
  const [run, setRun] = useState<RunResponse | null>(null);
  const [molecule, setMolecule] = useState<MoleculeResponse | null>(null);
  const [moleculePending, setMoleculePending] = useState(false);
  const [result, setResult] = useState<RunResultResponse | null>(null);
  const [events, setEvents] = useState<RunEventResponse[]>([]);
  const [eventsPending, setEventsPending] = useState(false);
  const [resultPending, setResultPending] = useState(false);
  const [pendingAction, setPendingAction] = useState<RunAction | null>(null);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [confirmingPause, setConfirmingPause] = useState(false);
  const [confirmingRestart, setConfirmingRestart] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const lastSequenceRef = useRef<number>(0);
  const seenSequencesRef = useRef<Set<number>>(new Set());

  const { sseDisconnected, resetSseSubscriptionState } = useRunSseSubscription({
    runId,
    run,
    setRun,
    setResult,
    setEvents,
    lastSequenceRef,
    seenSequencesRef,
  });

  useEffect(() => {
    let active = true;
    const isActive = () => active;

    async function loadRun() {
      setLoading(true);
      setLoadError(null);
      setRun(null);
      setMolecule(null);
      setMoleculePending(false);
      setResult(null);
      setEvents([]);
      setEventsPending(false);
      setResultPending(false);
      resetSseSubscriptionState();
      lastSequenceRef.current = 0;
      seenSequencesRef.current.clear();

      try {
        const fetchedRun = await getRun(runId);
        if (!active) return;

        setRun(fetchedRun);
        setLoading(false);

        setEventsPending(true);
        setMoleculePending(true);
        void loadRunEvents({
          runId,
          isActive,
          setEvents,
          setEventsPending,
          lastSequenceRef,
          seenSequencesRef,
        });

        void loadRunMolecule(fetchedRun.molecule_id, isActive, setMolecule, setMoleculePending);

        if (fetchedRun.status === "COMPLETED") {
          setResultPending(true);
          void loadRunResult(runId, isActive, setResult, setResultPending);
        }
      } catch (err) {
        if (!active) return;
        logAppError("run-detail.load", "Failed to load run detail.", err, { runId });
        setLoadError(err instanceof Error ? err : new Error(getErrorMessage(err, String(err))));
        setLoading(false);
      }
    }

    void loadRun();

    return () => {
      active = false;
    };
  }, [resetSseSubscriptionState, runId]);

  async function handleCancelConfirm() {
    if (!run) return;
    setPendingAction("cancel");
    setActionError(null);
    setConfirmingCancel(false);
    try {
      const updated = await cancelRun(run.id);
      setRun((prev) => (prev ? { ...prev, status: updated.status } : prev));
    } catch (err) {
      logAppError("run-detail.actions", "Failed to cancel run.", err, {
        runId: run.id,
        action: "cancel",
      });
      setActionError(getErrorMessage(err, "Failed to cancel run. Please try again."));
    } finally {
      setPendingAction(null);
    }
  }

  async function handlePause() {
    if (!run) return;
    setPendingAction("pause");
    setActionError(null);
    setConfirmingPause(false);
    try {
      const updated = await pauseRun(run.id);
      setRun((prev) => (prev ? { ...prev, status: updated.status } : prev));
    } catch (err) {
      logAppError("run-detail.actions", "Failed to pause run.", err, {
        runId: run.id,
        action: "pause",
      });
      setActionError(getErrorMessage(err, "Failed to pause run. Please try again."));
    } finally {
      setPendingAction(null);
    }
  }

  async function handleResume() {
    if (!run) return;
    setPendingAction("resume");
    setActionError(null);
    try {
      const updated = await resumeRun(run.id);
      setRun((prev) => (prev ? { ...prev, status: updated.status } : prev));
    } catch (err) {
      logAppError("run-detail.actions", "Failed to resume run.", err, {
        runId: run.id,
        action: "resume",
      });
      setActionError(getErrorMessage(err, "Failed to resume run. Please try again."));
    } finally {
      setPendingAction(null);
    }
  }

  async function handleRestartConfirm() {
    if (!run) return;
    setPendingAction("restart");
    setActionError(null);
    setConfirmingRestart(false);
    try {
      const restarted = await restartRun(run.id);
      if (isFullRunResponse(restarted)) {
        setRun(restarted);
      }

      const targetRunId = getRestartTargetId(restarted);
      if (targetRunId !== run.id) {
        void navigate({ to: "/runs/$runId", params: { runId: targetRunId } });
      } else if (!isFullRunResponse(restarted)) {
        setRun((prev) => (prev ? { ...prev, status: restarted.status } : prev));
      }
    } catch (err) {
      logAppError("run-detail.actions", "Failed to restart run.", err, {
        runId: run.id,
        action: "restart",
      });
      setActionError(getErrorMessage(err, "Failed to restart run. Please try again."));
    } finally {
      setPendingAction(null);
    }
  }

  const isRunning = run ? isRunExecuting(run.status) : false;
  const activityLabel = run ? getRunActivityLabel(run.status, sseDisconnected) : null;
  const isCancellable = run ? CANCELLABLE_STATUSES.has(run.status) : false;
  const isPausable = run ? PAUSABLE_STATUSES.has(run.status) : false;
  const isResumable = run ? RESUMABLE_STATUSES.has(run.status) : false;
  const isRestartable = run ? RESTARTABLE_STATUSES.has(run.status) : false;

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto">
      <button
        type="button"
        onClick={goBack}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors w-fit"
        aria-label="Go back"
      >
        <ChevronLeft className="size-4" />
        Back
      </button>

      {loading && <RunDetailLoadingSkeleton />}

      {loadError && (
        <PageErrorState {...getErrorPresentation(loadError, "this run")} onRetry={null} />
      )}

      {!loading && !loadError && run && (
        <>
          <RunHeader
            run={run}
            activityLabel={activityLabel}
            isCancellable={isCancellable}
            isPausable={isPausable}
            isResumable={isResumable}
            isRestartable={isRestartable}
            pendingAction={pendingAction}
            confirmingCancel={confirmingCancel}
            confirmingPause={confirmingPause}
            confirmingRestart={confirmingRestart}
            actionError={actionError}
            onConfirmingCancelChange={setConfirmingCancel}
            onConfirmingPauseChange={setConfirmingPause}
            onConfirmingRestartChange={setConfirmingRestart}
            onCancelConfirm={handleCancelConfirm}
            onPauseConfirm={handlePause}
            onResume={handleResume}
            onRestartConfirm={handleRestartConfirm}
          />

          <ResultsDashboard
            run={run}
            result={result}
            events={events}
            molecule={molecule}
            moleculePending={moleculePending}
            isRunning={isRunning}
            activityLabel={activityLabel}
            sseDisconnected={sseDisconnected}
            eventsPending={eventsPending}
            resultPending={resultPending}
          />
        </>
      )}
    </div>
  );
}

export default RunDetail;
