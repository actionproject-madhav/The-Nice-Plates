/** Landing + sign-in. The only page an unauthenticated visitor sees. */

import { useEffect, useState } from "react";
import { GoogleButton, useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { Icon } from "../components/Icon";
import { ChunkDiagram, TakeDiagram, CoachDiagram, HeroScore } from "../components/Notation";

/** The product in three moves. Each one is a drawing; the words are a caption
 *  on it, not a substitute for it. */
const STEPS = [
  { n: "01", label: "Chunk it", figure: <ChunkDiagram /> },
  { n: "02", label: "Record it", figure: <TakeDiagram /> },
  { n: "03", label: "Ask about it", figure: <CoachDiagram /> },
];

/** Google is optional. When it isn't configured the way in is the plain one,
 *  and it is the page's single accent-filled action either way. */
const GOOGLE = Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID);

export function SignIn() {
  const { error, signInAsDev } = useAuth();
  const [reachable, setReachable] = useState(true);

  useEffect(() => {
    api
      .health()
      .then(() => setReachable(true))
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

      <div style={{ marginTop: 34 }}>
        {GOOGLE ? (
          <GoogleButton />
        ) : (
          <button type="button" className="btn btn-primary" onClick={() => void signInAsDev()}>
            Start practising <Icon name="arrow" />
          </button>
        )}
      </div>

      {error && (
        <p className="notice" data-tone="bad" style={{ marginTop: 24 }}>
          {error}
        </p>
      )}

      {!reachable && (
        <p className="notice" data-tone="bad" style={{ marginTop: 24 }}>
          Can’t reach the server right now.
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

    </div>
  );
}
