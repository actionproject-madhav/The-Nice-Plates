/** The practice log. The page people open most, so it costs two requests. */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Progress, type Session, type Piece } from "../lib/api";
import { Ledger } from "../components/Ledger";
import { duration, relativeDay } from "../lib/format";
import { useAuth } from "../lib/auth";

export function Dashboard() {
  const { user } = useAuth();
  const [progress, setProgress] = useState<Progress | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [pieces, setPieces] = useState<Piece[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.progress(), api.listSessions(), api.listPieces()])
      .then(([p, s, l]) => {
        setProgress(p);
        setSessions(s);
        setPieces(l);
      })
      .catch((e) => setError(e.message));
  }, []);

  const titleOf = (id: string | null) =>
    pieces.find((p) => p.id === id)?.title ?? "Free practice";

  if (error) return <p className="notice" data-tone="bad">{error}</p>;
  if (!progress) return <p className="muted">Loading…</p>;

  const played = progress.total_sessions > 0;

  return (
    <div className="reveal">
      <p className="eyebrow">{user?.name ?? "Practice log"}</p>
      <h1 className="display title" style={{ marginBottom: 32 }}>
        {played
          ? `${duration(progress.total_minutes)} on the bench`
          : "Nothing logged yet"}
      </h1>

      {played ? (
        <>
          <Ledger days={progress.recent_days} span={30} />

          <dl className="readout" style={{ marginTop: 40 }}>
            <Stat label="Streak" value={progress.current_streak_days} unit="d" />
            <Stat label="Longest" value={progress.longest_streak_days} unit="d" />
            <Stat label="Sessions" value={progress.total_sessions} />
            <Stat label="Pieces" value={progress.pieces_practiced} />
          </dl>
        </>
      ) : (
        <div className="empty">
          <Link to="/library" className="btn btn-primary">
            Add your first piece
          </Link>
        </div>
      )}

      {sessions.length > 0 && (
        <>
          <hr className="rule" />
          <p className="eyebrow">Recent sessions</p>
          <div className="stack">
            {sessions.slice(0, 12).map((s) => (
              <div className="entry" key={s.id}>
                <span className="entry-title">{titleOf(s.piece_id)}</span>
                <span className="entry-meta">
                  {s.duration_seconds ? `${Math.round(s.duration_seconds / 60)} min` : "—"}
                </span>
                <span className="entry-meta muted">{relativeDay(s.started_at)}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, unit }: { label: string; value: number; unit?: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        {value}
        {unit && <span>{unit}</span>}
      </dd>
    </div>
  );
}
