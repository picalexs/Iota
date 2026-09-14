import { RunsListView } from "./components/runs-list-view";
import { useRunsListController } from "./state/use-runs-list-controller";

export function RunsList() {
  const controller = useRunsListController();
  return <RunsListView controller={controller} />;
}
