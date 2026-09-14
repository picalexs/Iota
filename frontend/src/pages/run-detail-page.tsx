import { useParams } from "@tanstack/react-router";
import { RunDetail } from "@/components/runs/run-detail";

export function RunDetailPage() {
  const { runId } = useParams({ from: "/runs/$runId" });

  if (!runId) {
    return (
      <div className="flex flex-col gap-6 max-w-5xl mx-auto">
        <p role="alert" className="text-destructive text-sm">
          No run ID provided.
        </p>
      </div>
    );
  }

  return <RunDetail runId={runId} />;
}

export default RunDetailPage;
