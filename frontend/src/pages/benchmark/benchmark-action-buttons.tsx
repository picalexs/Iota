import { Pause, Play, Plus, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

function BenchmarkActionButtonContent({
  pending,
  pendingLabel,
  idleLabel,
  idleIcon: IdleIcon,
}: Readonly<{
  pending: boolean;
  pendingLabel: string;
  idleLabel: string;
  idleIcon: typeof Play;
}>) {
  return pending ? (
    <>
      <Spinner />
      {pendingLabel}
    </>
  ) : (
    <>
      <IdleIcon className="h-4 w-4" />
      {idleLabel}
    </>
  );
}

export function BenchmarkPausedActions({
  actionInProgress,
  resumeInProgress,
  restartInProgress,
  onResumeBenchmark,
  onRestartBenchmark,
}: Readonly<{
  actionInProgress: boolean;
  resumeInProgress: boolean;
  restartInProgress: boolean;
  onResumeBenchmark: () => void;
  onRestartBenchmark: () => void;
}>) {
  return (
    <>
      <Button
        onClick={onResumeBenchmark}
        disabled={actionInProgress}
        aria-busy={resumeInProgress}
        className="min-w-[160px]"
      >
        <BenchmarkActionButtonContent
          pending={resumeInProgress}
          pendingLabel="Resuming..."
          idleLabel="Resume"
          idleIcon={Play}
        />
      </Button>

      <Button
        variant="outline"
        onClick={onRestartBenchmark}
        disabled={actionInProgress}
        aria-busy={restartInProgress}
      >
        <BenchmarkActionButtonContent
          pending={restartInProgress}
          pendingLabel="Restarting..."
          idleLabel="Restart"
          idleIcon={RotateCcw}
        />
      </Button>
    </>
  );
}

export function BenchmarkRunButton({
  runDisabled,
  running,
  onRunBenchmark,
}: Readonly<{
  runDisabled: boolean;
  running: boolean;
  onRunBenchmark: () => void;
}>) {
  return (
    <Button onClick={onRunBenchmark} disabled={runDisabled} className="min-w-[160px]">
      <BenchmarkActionButtonContent
        pending={running}
        pendingLabel="Running..."
        idleLabel="Run Benchmark"
        idleIcon={Plus}
      />
    </Button>
  );
}

export function BenchmarkPauseButton({
  pauseInProgress,
  onPauseBenchmark,
}: Readonly<{
  pauseInProgress: boolean;
  onPauseBenchmark: () => void;
}>) {
  return (
    <Button
      variant="outline"
      onClick={onPauseBenchmark}
      disabled={pauseInProgress}
      aria-busy={pauseInProgress}
    >
      <BenchmarkActionButtonContent
        pending={pauseInProgress}
        pendingLabel="Pausing..."
        idleLabel="Pause"
        idleIcon={Pause}
      />
    </Button>
  );
}
