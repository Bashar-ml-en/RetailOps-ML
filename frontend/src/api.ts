import type { PublicBenchmarkRun, RuntimeEvent, SystemBlueprint } from "./types";

const configuredApiBaseUrl = import.meta.env.VITE_API_URL?.replace(/\/+$/, "");
const apiBaseUrl = configuredApiBaseUrl ?? (import.meta.env.DEV ? "http://localhost:8000" : undefined);

export const hasBlueprintApi = Boolean(apiBaseUrl);

export async function fetchSystemBlueprint(): Promise<SystemBlueprint> {
  if (!apiBaseUrl) {
    throw new Error("No system blueprint API is configured for this deployment");
  }

  const response = await fetch(`${apiBaseUrl}/system/blueprint`);
  if (!response.ok) {
    throw new Error(`Blueprint API returned ${response.status}`);
  }
  return response.json() as Promise<SystemBlueprint>;
}

export async function fetchPublicBenchmarkRuns(): Promise<PublicBenchmarkRun[]> {
  if (!apiBaseUrl) {
    throw new Error("No RetailOps runtime API is configured for this deployment");
  }
  const response = await fetch(`${apiBaseUrl}/v1/public-benchmark-runs`);
  if (!response.ok) {
    throw new Error(`Runtime API returned ${response.status}`);
  }
  const payload = await response.json() as { runs: PublicBenchmarkRun[] };
  return payload.runs;
}

export async function fetchPublicBenchmarkEvents(runId: string): Promise<RuntimeEvent[]> {
  if (!apiBaseUrl) {
    throw new Error("No RetailOps runtime API is configured for this deployment");
  }
  const response = await fetch(`${apiBaseUrl}/v1/public-benchmark-runs/${encodeURIComponent(runId)}/events`);
  if (!response.ok) {
    throw new Error(`Runtime events API returned ${response.status}`);
  }
  const payload = await response.json() as { events: RuntimeEvent[] };
  return payload.events;
}
