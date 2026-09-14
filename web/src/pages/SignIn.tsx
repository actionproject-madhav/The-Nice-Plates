/** Landing + sign-in. The only page an unauthenticated visitor sees. */

import { useEffect, useState } from "react";
import { GoogleButton, useAuth } from "../lib/auth";
import { api, type ReadyCheck } from "../lib/api";
import { ChunkDiagram, TakeDiagram, CoachDiagram, HeroScore } from "../components/Notation";

/** The product in three moves. Each one is a drawing; the words are a caption
 *  on it, not a substitute for it. */
const STEPS = [
  { n: "01", label: "Chunk it", figure: <ChunkDiagram /> },
  { n: "02", label: "Record it", figure: <TakeDiagram /> },
  { n: "03", label: "Ask about it", figure: <CoachDiagram /> },
];

export function SignIn() {
  const { error, signInAsDev } = useAuth();
  const [ready, setReady] = useState<ReadyCheck | null>(null);
  const [reachable, setReachable] = useState<boolean | null>(null);

  useEffect(() => {
    api
      .health()
      .then((r) => {
        setReady(r);
        setReachable(true);
      })
      .catch(() => setReachable(false));
  }, []);

  return (
    <div className="reveal">
      <p className="eyebrow">Practice log for musicians</p>
      <h1 className="display hero">
        Play it.
        <br />
        Hear what
        <br />
        actually happened.
      </h1>

      <HeroScore />

      <p className="lede" style={{ marginTop: 20 }}>
        Record a take. Get back the bars you rushed and the tempo you actually held.
      </p>

      <div style={{ marginTop: 36, display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
        <GoogleButton />
        {import.meta.env.DEV && (
          <button type="button" className="btn btn-quiet btn-sm" onClick={() => void signInAsDev()}>
            Dev sign-in
          </button>
        )}
      </div>

      {error && (
        <p className="notice" data-tone="bad" style={{ marginTop: 24 }}>
          {error}
        </p>
      )}

      {reachable === false && (
        <p className="notice" style={{ marginTop: 24 }}>
          The API isn’t reachable from here. Set <span className="mono">VITE_API_BASE_URL</span> to
          your deployed API, or run it locally on port 8000.
        </p>
      )}

      <div className="strip">
        {STEPS.map((step) => (
          <figure key={step.n}>
            {step.figure}
            <figcaption>
              <b>{step.n}</b>
              {step.label}
            </figcaption>
          </figure>
        ))}
      </div>

      {ready && ready.status !== "ok" && (
        <p className="small muted" style={{ marginTop: 40 }}>
          API status: <span className="mono">{ready.status}</span> —{" "}
          {Object.entries(ready.checks)
            .filter(([, c]) => !c.ok)
            .map(([name]) => name)
            .join(", ")}{" "}
          not configured.
        </p>
      )}
    </div>
  );
}
