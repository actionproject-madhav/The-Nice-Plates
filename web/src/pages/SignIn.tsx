/** Landing + sign-in. The only page an unauthenticated visitor sees. */

import { useEffect, useState } from "react";
import { GoogleButton, useAuth } from "../lib/auth";
import { api, type ReadyCheck } from "../lib/api";

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

      <p className="lede" style={{ marginTop: 28 }}>
        Record a take, and get back the bars you rushed, the notes you missed, and the tempo you
        actually held — not the one you meant to. Every session lands in a log you can read at a
        glance.
      </p>

      <div style={{ marginTop: 40, display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
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

      <hr className="rule" />

      <div className="row" style={{ gap: 48 }}>
        <Column
          kicker="Chunk it"
          body="Split a score into bars you can actually drill, and work one at a time instead of running the whole thing badly."
        />
        <Column
          kicker="Record it"
          body="A take goes straight to storage and comes back with pitch, timing, and a list of the bars that need another pass."
        />
        <Column
          kicker="Ask about it"
          body="The coach reads your own history before it answers, so it can point at a specific week and a specific bar."
        />
      </div>

      {ready && ready.status !== "ok" && (
        <p className="small muted" style={{ marginTop: 48 }}>
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

function Column({ kicker, body }: { kicker: string; body: string }) {
  return (
    <div style={{ flex: "1 1 220px" }}>
      <p className="eyebrow">{kicker}</p>
      <p className="small muted" style={{ margin: 0, maxWidth: "34ch" }}>
        {body}
      </p>
    </div>
  );
}
