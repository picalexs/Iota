import { Cloud, Cpu, Server, type LucideIcon } from "lucide-react";

import { FormField } from "@/components/forms/form-field";
import { Spinner } from "@/components/ui/spinner";
import { SelectableCard } from "@/components/ui/selectable-card";
import { selectableCardIconClassName } from "@/lib/interactive-styles";
import { cn } from "@/lib/utils";
import type { IbmBackendWarmupProgress } from "@/lib/ibm-profile-events";
import type { BackendCapability, BackendTarget } from "@/types/run";

import { getBackendCardStateText, isBackendSelectable } from "./backend-card-state";
import { BACKEND_LABELS } from "./backend-section-shared";

const BACKEND_CARDS = [
  {
    value: "statevector" as BackendTarget,
    icon: Cpu,
  },
  {
    value: "aer_simulator" as BackendTarget,
    icon: Server,
  },
  {
    value: "ibm_runtime" as BackendTarget,
    icon: Cloud,
  },
];

type BackendCardConfig = {
  value: BackendTarget;
  icon: LucideIcon;
};

interface BackendTargetCardsProps {
  selectedValue: BackendTarget | null;
  disabled?: boolean;
  capabilities: BackendCapability[];
  capabilitiesLoading?: boolean;
  capabilitiesRefreshing?: boolean;
  capabilitiesWarmupProgress?: IbmBackendWarmupProgress | null;
  capabilitiesError?: string | null;
  error?: string;
  onSelect: (target: BackendTarget) => void;
}

export function BackendTargetCards({
  selectedValue,
  disabled,
  capabilities,
  capabilitiesLoading,
  capabilitiesRefreshing,
  capabilitiesWarmupProgress,
  capabilitiesError,
  error,
  onSelect,
}: BackendTargetCardsProps) {
  return (
    <FormField
      label="Backend Target"
      htmlFor="backend-option-statevector"
      required
      error={error}
      help={{
        short: "Choose the execution target. Aer and IBM Runtime expand into backend pickers.",
        anchor: "backend_target",
      }}
    >
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {BACKEND_CARDS.map((card) => {
          const capability = capabilities.find((cap) => cap.target === card.value);
          return (
            <BackendTargetCard
              key={card.value}
              card={card}
              selectedValue={selectedValue}
              disabled={disabled}
              capability={capability}
              capabilitiesLoading={capabilitiesLoading}
              capabilitiesRefreshing={capabilitiesRefreshing}
              capabilitiesWarmupProgress={capabilitiesWarmupProgress}
              onSelect={onSelect}
            />
          );
        })}
      </div>
      {capabilitiesError != null && (
        <p className="mt-2 text-xs text-muted-foreground">{capabilitiesError}</p>
      )}
    </FormField>
  );
}

function BackendTargetCard({
  card,
  selectedValue,
  disabled,
  capability,
  capabilitiesLoading,
  capabilitiesRefreshing,
  capabilitiesWarmupProgress,
  onSelect,
}: {
  card: BackendCardConfig;
  selectedValue: BackendTarget | null;
  disabled?: boolean;
  capability: BackendCapability | undefined;
  capabilitiesLoading?: boolean;
  capabilitiesRefreshing?: boolean;
  capabilitiesWarmupProgress?: IbmBackendWarmupProgress | null;
  onSelect: (target: BackendTarget) => void;
}) {
  const Icon = card.icon;
  const labels = BACKEND_LABELS[card.value];
  const selectable = isBackendSelectable(capability);
  const cardDisabled = Boolean(disabled || !selectable);
  const stateText = getBackendCardStateText({
    value: card.value,
    capability,
    selectable,
    capabilitiesLoading,
    capabilitiesRefreshing,
    capabilitiesWarmupProgress,
  });
  const isIbmBusy = Boolean(
    (capabilitiesLoading || capabilitiesRefreshing) && card.value === "ibm_runtime",
  );

  return (
    <SelectableCard
      id={`backend-option-${card.value}`}
      selected={selectedValue === card.value && !cardDisabled}
      disabled={cardDisabled}
      aria-pressed={selectedValue === card.value && !cardDisabled}
      onClick={() => !cardDisabled && onSelect(card.value)}
      className="flex-col items-start gap-3 text-sm"
    >
      <div className={selectableCardIconClassName}>
        <Icon className="size-4" />
      </div>
      <div className="flex flex-col gap-1">
        <span className="font-semibold">{labels.label}</span>
        <span
          className={cn(
            "text-muted-foreground",
            !selectable && !capabilitiesLoading && "text-amber-600",
          )}
        >
          {isIbmBusy ? (
            <span className="inline-flex items-center gap-1.5" role="status" aria-live="polite">
              <Spinner className="size-3" />
              {stateText}
            </span>
          ) : (
            stateText
          )}
        </span>
      </div>
    </SelectableCard>
  );
}
