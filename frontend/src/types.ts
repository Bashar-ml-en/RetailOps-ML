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

export interface PlannerBriefFinding {
  statement: string;
  evidence_refs: string[];
}

/** Persisted only after the deterministic Planner Brief Policy accepts it. */
export interface PublicPlannerBrief {
  planner_brief_schema_version: string;
  planner_brief_id: string;
  run_id: string;
  source_mode: "PUBLIC_BENCHMARK";
  status: "PASS" | "PASS_WITH_LIMITATIONS";
  headline: string;
  analysis_summary: string;
  forecast_findings: PlannerBriefFinding[];
  evidence_references: string[];
  limitations: string[];
  planner_verification_steps: string[];
  human_decision_required: boolean;
  prohibited_operations: string[];
  prompt_version: string;
  model_version: string;
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
