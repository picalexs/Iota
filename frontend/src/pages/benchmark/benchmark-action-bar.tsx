import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { BenchmarkOverflowActions } from "./benchmark-action-menu";
import {
  BenchmarkPausedActions,
  BenchmarkPauseButton,
  BenchmarkRunButton,
} from "./benchmark-action-buttons";

function BenchmarkCompletionSummary({
  total,
  completionRatio,
  done,
}: Readonly<{
  total: number;
  completionRatio: number;
  done: number;
}>) {
  if (total <= 0) return <div />;

  return (
    <div className="flex min-w-0 items-center gap-3">
      <Progress value={completionRatio} className="h-2 flex-1" />
      <div className="shrink-0 text-xs text-muted-foreground">
        {done} / {total} rows complete
      </div>
    </div>
  );
}

function BenchmarkResetResultsButton({
  showResetResults,
  onClear,
}: Readonly<{
  showResetResults: boolean;
  onClear: () => void;
}>) {
  if (showResetResults === false) return null;

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={onClear}
      className="h-8 lg:justify-self-end"
    >
      Clear results
    </Button>
  );
}

export function BenchmarkActionBar({
  hasPausedBenchmark,
  actionInProgress,
  resumeInProgress,
  restartInProgress,
  pauseInProgress,
  canPauseBenchmark,
  onResumeBenchmark,
  onRestartBenchmark,
  runDisabled,
  onRunBenchmark,
  running,
  onPauseBenchmark,
  onCancelBenchmark,
  showDeleteBenchmarkAction,
  deleteBenchmarkInProgress,
  onDeleteBenchmark,
  total,
  completionRatio,
  done,
  showResetResults,
  onClear,
}: Readonly<{
  hasPausedBenchmark: boolean;
  actionInProgress: boolean;
  resumeInProgress: boolean;
  restartInProgress: boolean;
  pauseInProgress: boolean;
  canPauseBenchmark: boolean;
  onResumeBenchmark: () => void;
  onRestartBenchmark: () => void;
  runDisabled: boolean;
  onRunBenchmark: () => void;
  running: boolean;
  onPauseBenchmark: () => void;
  onCancelBenchmark: () => void;
  showDeleteBenchmarkAction: boolean;
  deleteBenchmarkInProgress: boolean;
  onDeleteBenchmark?: () => void;
  total: number;
  completionRatio: number;
  done: number;
  showResetResults: boolean;
  onClear: () => void;
}>) {
  return (
    <div className="grid gap-3 border-t border-border/70 pt-4 lg:grid-cols-[auto_minmax(0,1fr)_auto] lg:items-center">
      <div className="flex flex-wrap items-center gap-3">
        {hasPausedBenchmark ? (
          <BenchmarkPausedActions
            actionInProgress={actionInProgress}
            resumeInProgress={resumeInProgress}
            restartInProgress={restartInProgress}
            onResumeBenchmark={onResumeBenchmark}
            onRestartBenchmark={onRestartBenchmark}
          />
        ) : (
          <BenchmarkRunButton
            runDisabled={runDisabled}
            running={running}
            onRunBenchmark={onRunBenchmark}
          />
        )}

        {canPauseBenchmark ? (
          <BenchmarkPauseButton
            pauseInProgress={pauseInProgress}
            onPauseBenchmark={onPauseBenchmark}
          />
        ) : null}

        {running ? (
          <Button variant="outline" onClick={onCancelBenchmark}>
            Cancel
          </Button>
        ) : null}

        <BenchmarkOverflowActions
          hasPausedBenchmark={hasPausedBenchmark}
          actionInProgress={actionInProgress}
          pauseInProgress={pauseInProgress}
          resumeInProgress={resumeInProgress}
          restartInProgress={restartInProgress}
          canPauseBenchmark={canPauseBenchmark}
          running={running}
          showDeleteBenchmarkAction={showDeleteBenchmarkAction}
          deleteBenchmarkInProgress={deleteBenchmarkInProgress}
          onPauseBenchmark={onPauseBenchmark}
          onResumeBenchmark={onResumeBenchmark}
          onRestartBenchmark={onRestartBenchmark}
          onCancelBenchmark={onCancelBenchmark}
          onDeleteBenchmark={onDeleteBenchmark}
        />
      </div>

      <BenchmarkCompletionSummary total={total} completionRatio={completionRatio} done={done} />

      <BenchmarkResetResultsButton showResetResults={showResetResults} onClear={onClear} />
    </div>
  );
}
