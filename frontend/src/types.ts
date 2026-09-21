export type BlueprintState =
  | "CONTRACT_DEFINED"
  | "DESIGNED"
  | "ENFORCED_BY_POLICY"
  | "IMPLEMENTED"
  | "PARTIAL"
  | "PLANNED";

export interface BlueprintStage {
  id: string;
  title: string;
  state: BlueprintState;
  owner: string;
  output: string;
}

export interface BlueprintAgent {
  id: string;
  name: string;
  responsibility: string;
  parallel_group: string;
  state: BlueprintState;
}

export interface BlueprintControl {
  title: string;
  detail: string;
  state: BlueprintState;
}

export interface SystemBlueprint {
  blueprint_version: string;
  mode: "ARCHITECTURE_BLUEPRINT";
  live_workloads: "NONE";
  truthful_status: {
    implemented_now: string[];
    not_running_yet: string[];
  };
  stages: BlueprintStage[];
  agents: BlueprintAgent[];
  lifecycle: string[];
  controls: BlueprintControl[];
}

export interface RuntimeEvent {
  sequence: number;
  name: string;
  occurred_at: string;
  detail: string;
  evidence_refs: string[];
}

export interface PublicBenchmarkRun {
  run_id: string;
  source_mode: "PUBLIC_BENCHMARK";
  data_classification: "PUBLIC_BENCHMARK";
  status: string;
  selection_id: string;
  created_at: string;
  updated_at: string;
  attempt_count: number;
  outcome: {
    status?: string;
    selection?: string;
    selected_model_version?: string;
    metrics?: Record<string, number>;
    limitations?: string[];
    next_action?: string;
  } | null;
  limitations: string[];
  prohibited_operations: string[];
}
