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
