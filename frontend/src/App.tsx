import { useEffect, useMemo, useState } from "react";

import {
  fetchPublicBenchmarkEvents,
  fetchPublicBenchmarkRuns,
  fetchSystemBlueprint,
  hasBlueprintApi,
} from "./api";
import { fallbackBlueprint } from "./blueprint";
import type { BlueprintState, PublicBenchmarkRun, RuntimeEvent, SystemBlueprint } from "./types";

const operatingSignals = [
  { label: "Execution mode", value: "Local public runtime", detail: "Only persisted API runs and worker events are rendered; no hidden workload is represented as live." },
  { label: "Evidence rule", value: "Versioned scope", detail: "Every specialist receives the same declared evidence bundle." },
  { label: "Decision authority", value: "Human planner", detail: "No purchase, transfer, price, or supplier action is automated." },
  { label: "Failure posture", value: "Inconclusive", detail: "Weak coverage or proof stops a case instead of inventing certainty." },
];

function displayState(state: BlueprintState): string {
  return state.replaceAll("_", " ").toLowerCase();
}

export default function App() {
  const [blueprint, setBlueprint] = useState<SystemBlueprint>(fallbackBlueprint);
  const [source, setSource] = useState(
    hasBlueprintApi ? "Connecting to blueprint API" : "Embedded architecture blueprint",
  );
  const [selectedStageId, setSelectedStageId] = useState(fallbackBlueprint.stages[0].id);
  const [runs, setRuns] = useState<PublicBenchmarkRun[]>([]);
  const [runtimeState, setRuntimeState] = useState(
    hasBlueprintApi ? "Loading persisted runtime events" : "Runtime API is not configured",
  );
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [events, setEvents] = useState<RuntimeEvent[]>([]);

  useEffect(() => {
    if (!hasBlueprintApi) {
      return;
    }

    let isCurrent = true;
    fetchSystemBlueprint()
      .then((nextBlueprint) => {
        if (isCurrent) {
          setBlueprint(nextBlueprint);
          setSource("Versioned blueprint API connected");
        }
      })
      .catch(() => {
        if (isCurrent) {
          setSource("Embedded blueprint — API unavailable");
        }
      });

    return () => {
      isCurrent = false;
    };
  }, []);

  const refreshRuns = () => {
    if (!hasBlueprintApi) {
      return;
    }
    setRuntimeState("Loading persisted runtime events");
    fetchPublicBenchmarkRuns()
      .then((nextRuns) => {
        setRuns(nextRuns);
        setSelectedRunId((current) => current && nextRuns.some((run) => run.run_id === current)
          ? current
          : (nextRuns[0]?.run_id ?? null));
        setRuntimeState(nextRuns.length ? "Persisted runtime API connected" : "No persisted benchmark runs yet");
      })
      .catch(() => setRuntimeState("Runtime API is unavailable — no run state is shown"));
  };

  useEffect(() => {
    refreshRuns();
    if (!hasBlueprintApi) {
      return undefined;
    }
    const refreshTimer = window.setInterval(refreshRuns, 15_000);
    return () => window.clearInterval(refreshTimer);
  }, []);

  useEffect(() => {
    if (!selectedRunId || !hasBlueprintApi) {
      setEvents([]);
      return;
    }
    let isCurrent = true;
    fetchPublicBenchmarkEvents(selectedRunId)
      .then((nextEvents) => {
        if (isCurrent) {
          setEvents(nextEvents);
        }
      })
      .catch(() => {
        if (isCurrent) {
          setEvents([]);
        }
      });
    return () => {
      isCurrent = false;
    };
  }, [selectedRunId, runs]);

  const selectedStage = useMemo(
    () => blueprint.stages.find((stage) => stage.id === selectedStageId) ?? blueprint.stages[0],
    [blueprint.stages, selectedStageId],
  );
  const parallelAgents = blueprint.agents.filter((agent) => agent.parallel_group === "evidence-review");
  const gateAgents = blueprint.agents.filter((agent) => agent.parallel_group === "release-gate");
  const selectedStageGate = selectedStage.state === "IMPLEMENTED"
    ? "Implemented locally: this gate records a typed artifact but has no live workload, production deployment, or automated action."
    : "Not operating yet: missing proof will block this stage when its implementation begins.";

  return (
    <main className="control-room">
      <div className="ambient ambient-one" aria-hidden="true" />
      <div className="ambient ambient-two" aria-hidden="true" />

      <header className="topbar">
        <a className="brand" href="#overview" aria-label="RetailOps ML overview">
          <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
          <span>RetailOps <b>ML</b></span>
        </a>
        <nav className="topnav" aria-label="Control room sections">
          <a href="#architecture">Architecture</a>
          <a href="#runtime">Runtime</a>
          <a href="#agents">Agents</a>
          <a href="#lifecycle">Lifecycle</a>
          <a href="#controls">Gates</a>
        </nav>
        <span className="source-chip"><i aria-hidden="true" />{source}</span>
      </header>

      <section className="hero" id="overview">
        <div className="hero-copy">
          <div className="command-row">
            <span>CONTROL PLANE / 001</span>
            <span className="command-rule">{blueprint.mode.replaceAll("_", " ")}</span>
          </div>
          <p className="eyebrow">Evidence-first retail operations</p>
          <h1>Retail decisions <span>need proof,</span> not theatre.</h1>
          <p className="lede">
            A professional operating model for turning authorised retail data into reviewable
            demand and inventory cases—through controlled ML, typed specialists, and a final
            human decision boundary.
          </p>
          <div className="hero-actions">
            <a className="primary-link" href="#architecture">Inspect the operating map <span aria-hidden="true">↓</span></a>
            <a className="quiet-link" href="#controls">See the release gates</a>
          </div>
        </div>

        <aside className="system-card" aria-label="Current system truth">
          <div className="system-card-head">
            <div><span className="micro-label">SYSTEM TRUTH</span><strong>RetailOps / local public runtime</strong></div>
            <span className="truth-pill">NO LIVE JOBS</span>
          </div>
          <div className="signal-field" aria-hidden="true">
            <span className="signal-node node-a" /><span className="signal-node node-b" />
            <span className="signal-node node-c" /><span className="signal-node node-d" />
            <span className="signal-line line-a" /><span className="signal-line line-b" />
            <span className="signal-line line-c" />
            <span className="signal-core">R</span>
          </div>
          <dl className="system-facts">
            <div><dt>Live workloads</dt><dd>{blueprint.live_workloads === "NONE" ? "None" : blueprint.live_workloads}</dd></div>
            <div><dt>Release posture</dt><dd>Explicit worker required</dd></div>
            <div><dt>Final authority</dt><dd>Retail planner</dd></div>
          </dl>
          <p className="system-caption">The interface is an inspectable operating contract, not a simulated production run.</p>
        </aside>
      </section>

      <section className="signal-rail" aria-label="Operating principles">
        {operatingSignals.map((signal, index) => (
          <article className="signal-card" key={signal.label}>
            <span className="signal-number">0{index + 1}</span>
            <p>{signal.label}</p>
            <h2>{signal.value}</h2>
            <small>{signal.detail}</small>
          </article>
        ))}
      </section>

      <section className="runtime-section" id="runtime" aria-labelledby="runtime-heading">
        <div className="section-heading">
          <div><p className="eyebrow">Persisted execution</p><h2 id="runtime-heading">Real public runs, never simulated timelines.</h2></div>
          <div className="runtime-heading-actions">
            <p>{runtimeState}</p>
            <button className="quiet-button" onClick={refreshRuns} type="button" disabled={!hasBlueprintApi}>Refresh</button>
          </div>
        </div>
        {!hasBlueprintApi ? (
          <div className="runtime-empty">
            This static deployment has no backend runtime. Configure <code>VITE_API_URL</code> to inspect persisted runs; no fallback result is displayed.
          </div>
        ) : runs.length === 0 ? (
          <div className="runtime-empty">
            No public benchmark run has been persisted. The server queues an explicit selection and a separate worker processes it from a server-configured public source.
          </div>
        ) : (
          <div className="runtime-shell">
            <div className="run-list" aria-label="Persisted public benchmark runs">
              {runs.map((run) => (
                <button
                  className={`run-card ${run.run_id === selectedRunId ? "is-selected" : ""}`}
                  key={run.run_id}
                  onClick={() => setSelectedRunId(run.run_id)}
                  type="button"
                >
                  <span className="micro-label">PUBLIC BENCHMARK</span>
                  <strong>{run.selection_id}</strong>
                  <em className={`state state-${run.status.toLowerCase()}`}>{displayState(run.status as BlueprintState)}</em>
                  <small>{new Date(run.updated_at).toLocaleString()}</small>
                </button>
              ))}
            </div>
            <aside className="runtime-detail" aria-live="polite">
              {selectedRunId ? (
                <>
                  <div className="detail-topline"><span className="micro-label">IMMUTABLE EVENT TRAIL</span><span>{events.length} events</span></div>
                  <ol className="runtime-events">
                    {events.map((event) => (
                      <li key={`${event.sequence}-${event.name}`}>
                        <div><strong>{event.name}</strong><time>{new Date(event.occurred_at).toLocaleString()}</time></div>
                        <p>{event.detail}</p>
                        {event.evidence_refs.length > 0 && <small>{event.evidence_refs.join(" · ")}</small>}
                      </li>
                    ))}
                  </ol>
                </>
              ) : <p>No persisted run is selected.</p>}
            </aside>
          </div>
        )}
      </section>

      <section className="maturity-section" aria-label="Current delivery maturity">
        <article className="maturity-card foundation-card">
          <div className="maturity-head"><p className="card-kicker">Implemented foundation</p><span>NOW</span></div>
          <h2>Controls you can inspect today.</h2>
          <ul>{blueprint.truthful_status.implemented_now.map((item) => <li key={item}>{item}</li>)}</ul>
        </article>
        <article className="maturity-card horizon-card">
          <div className="maturity-head"><p className="card-kicker">Build horizon</p><span>NEXT</span></div>
          <h2>Workloads that still require proof.</h2>
          <ul>{blueprint.truthful_status.not_running_yet.map((item) => <li key={item}>{item}</li>)}</ul>
        </article>
      </section>

      <section className="architecture-section" id="architecture" aria-labelledby="flow-heading">
        <div className="section-heading">
          <div><p className="eyebrow">Operating map</p><h2 id="flow-heading">One evidence trail. Seven accountable hand-offs.</h2></div>
          <p>Choose any stage to see the owner, required artifact, and current delivery posture.</p>
        </div>
        <div className="architecture-shell">
          <div className="stage-flow" aria-label="RetailOps system stages">
            {blueprint.stages.map((stage, index) => (
              <button
                className={`stage-node ${stage.id === selectedStage.id ? "is-selected" : ""}`}
                key={stage.id}
                onClick={() => setSelectedStageId(stage.id)}
                type="button"
                aria-pressed={stage.id === selectedStage.id}
              >
                <span className="stage-index">{String(index + 1).padStart(2, "0")}</span>
                <strong>{stage.title}</strong>
                <em className={`state state-${stage.state.toLowerCase()}`}>{displayState(stage.state)}</em>
              </button>
            ))}
          </div>
          <aside className="stage-detail" aria-live="polite">
            <div className="detail-topline"><span className="micro-label">SELECTED HAND-OFF</span><span className={`state state-${selectedStage.state.toLowerCase()}`}>{displayState(selectedStage.state)}</span></div>
            <h3>{selectedStage.title}</h3>
            <dl>
              <div><dt>Accountable owner</dt><dd>{selectedStage.owner}</dd></div>
              <div><dt>Required artifact</dt><dd>{selectedStage.output}</dd></div>
              <div><dt>Gate behavior</dt><dd>{selectedStageGate}</dd></div>
            </dl>
          </aside>
        </div>
      </section>

      <section className="agents-section" id="agents" aria-labelledby="agents-heading">
        <div className="section-heading">
          <div><p className="eyebrow">Specialist mesh</p><h2 id="agents-heading">Parallel review with a single evidence boundary.</h2></div>
          <p>This is the planned specialist topology. When implemented, parallel specialists increase coverage; they never bypass policy critique or planner approval.</p>
        </div>
        <div className="agent-orchestration">
          <div className="parallel-block">
            <div className="block-heading"><div><span className="micro-label">PARALLEL REVIEW GROUP</span><strong>Same versioned input scope</strong></div><span className="mesh-tag">4 SPECIALISTS</span></div>
            <div className="agent-grid">
              {parallelAgents.map((agent, index) => (
                <article className="agent-card" key={agent.id}>
                  <div className="agent-card-head"><span className="agent-id">A0{index + 1}</span><em className={`state state-${agent.state.toLowerCase()}`}>{displayState(agent.state)}</em></div>
                  <h3>{agent.name}</h3><p>{agent.responsibility}</p>
                </article>
              ))}
            </div>
          </div>
          <div className="convergence" aria-label="Evidence converges at the policy gate"><span>Typed evidence bundles</span><i aria-hidden="true" /><strong>Policy gate</strong></div>
          <div className="gate-block">
            <div className="block-heading"><div><span className="micro-label">RELEASE GATE</span><strong>Veto power retained</strong></div><span className="mesh-tag">2 AGENTS</span></div>
            {gateAgents.map((agent, index) => (
              <article className="gate-card" key={agent.id}>
                <div><span className="agent-id">G0{index + 1}</span><em className={`state state-${agent.state.toLowerCase()}`}>{displayState(agent.state)}</em></div>
                <h3>{agent.name}</h3><p>{agent.responsibility}</p>
              </article>
            ))}
            <article className="human-card"><span className="micro-label">NON-DELEGABLE AUTHORITY</span><h3>Retail planner approval</h3><p>The only actor allowed to approve, decline, or defer an operational action draft.</p></article>
          </div>
        </div>
      </section>

      <section className="lifecycle-section" id="lifecycle" aria-labelledby="lifecycle-heading">
        <div className="section-heading">
          <div><p className="eyebrow">ML lifecycle</p><h2 id="lifecycle-heading">Training and promotion are controlled—not a black box.</h2></div>
          <p>Chronology is protected at every evaluation point, including the locked final test period.</p>
        </div>
        <ol className="lifecycle-steps">
          {blueprint.lifecycle.map((step, index) => (
            <li key={step}><span>{String(index + 1).padStart(2, "0")}</span><p>{step}</p></li>
          ))}
        </ol>
      </section>

      <section className="controls-section" id="controls" aria-labelledby="controls-heading">
        <div className="section-heading">
          <div><p className="eyebrow">Reliability envelope</p><h2 id="controls-heading">A release is a chain of gates, not a button.</h2></div>
          <p>Every data, model, and decision artifact must remain reviewable after the fact.</p>
        </div>
        <div className="controls-grid">
          {blueprint.controls.map((control, index) => (
            <article className="control-card" key={control.title}>
              <div><span className="control-index">0{index + 1}</span><em className={`state state-${control.state.toLowerCase()}`}>{displayState(control.state)}</em></div>
              <h3>{control.title}</h3><p>{control.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="impact-band">
        <div><p className="eyebrow">Impact contract</p><h2>Measure operational value. Never manufacture certainty.</h2></div>
        <div><p>A pilot measures forecast error, qualified cases, planner response time, stockout days, and excess inventory against a declared baseline.</p><span>INCOMPLETE EVIDENCE → INCONCLUSIVE</span></div>
      </section>
    </main>
  );
}
