/**
 * Practice mode.
 *
 * The one page that exercises the whole pipeline: start a session, record with
 * MediaRecorder, PUT the blob straight to storage, then poll until the worker
 * has something to say.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api, putToStorage, type Feedback, type PieceDetail } from "../lib/api";
import { Icon } from "../components/Icon";
import { clock, percent } from "../lib/format";

type Phase = "idle" | "recording" | "uploading" | "analyzing" | "done" | "error";

export function Practice() {
  const { pieceId = "" } = useParams();
  const [params] = useSearchParams();

  const [piece, setPiece] = useState<PieceDetail | null>(null);
  const [sectionId, setSectionId] = useState<string | null>(params.get("section"));
  const [sessionId, setSessionId] = useState<string | null>(null);

  const [phase, setPhase] = useState<Phase>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [playback, setPlayback] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const ticker = useRef<number | null>(null);
  const sessionSeconds = useRef(0);

  useEffect(() => {
    api.getPiece(pieceId).then(setPiece).catch((e) => setMessage(e.message));
  }, [pieceId]);

  // Close the session on unmount so a navigated-away session isn't left open.
  useEffect(() => {
    return () => {
      if (ticker.current) window.clearInterval(ticker.current);
      recorder.current?.stream.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const start = useCallback(async () => {
    setMessage(null);
    setFeedback(null);
    setPlayback(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/mp4"; // Safari
      const rec = new MediaRecorder(stream, { mimeType: mime });
      chunks.current = [];
      rec.ondataavailable = (e) => e.data.size > 0 && chunks.current.push(e.data);
      rec.onstop = () => void upload(new Blob(chunks.current, { type: mime }), mime);

      let id = sessionId;
      if (!id) {
        const session = await api.startSession({
          piece_id: pieceId,
          section_id: sectionId ?? undefined,
          tempo_bpm: piece?.tempo_bpm ?? undefined,
        });
        id = session.id;
        setSessionId(id);
      }

      rec.start();
      recorder.current = rec;
      setPhase("recording");
      setElapsed(0);
      ticker.current = window.setInterval(() => {
        setElapsed((s) => s + 1);
        sessionSeconds.current += 1;
      }, 1000);
    } catch (e) {
      setPhase("error");
      setMessage(
        e instanceof DOMException
          ? "We need microphone access to record. Allow it and try again."
          : e instanceof Error
            ? e.message
            : "Couldn't start recording.",
      );
    }
    // `upload` is stable enough for this flow; re-creating it would restart the recorder.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pieceId, sectionId, sessionId, piece]);

  function stop() {
    if (ticker.current) window.clearInterval(ticker.current);
    recorder.current?.stop();
    recorder.current?.stream.getTracks().forEach((t) => t.stop());
    setPhase("uploading");
  }

  async function upload(blob: Blob, mime: string) {
    try {
      const ticket = await api.uploadUrl({
        filename: `take.${mime.includes("mp4") ? "m4a" : "webm"}`,
        content_type: mime,
        session_id: sessionId ?? undefined,
        piece_id: pieceId,
        section_id: sectionId ?? undefined,
      });
      await putToStorage(ticket, blob);
      await api.completeUpload(ticket.recording_id, blob.size, elapsed);
      setPhase("analyzing");
      await poll(ticket.recording_id);
    } catch (e) {
      setPhase("error");
      setMessage(e instanceof Error ? e.message : "That take didn't upload.");
    }
  }

  async function poll(recordingId: string) {
    const deadline = Date.now() + 90_000;
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 1500));
      const status = await api.recording(recordingId);
      if (status.status === "analyzed") {
        setFeedback(status.feedback);
        setPlayback(status.playback_url);
        setPhase("done");
        return;
      }
      if (status.status === "failed") {
        setPhase("error");
        setMessage(status.error ?? "We couldn't analyse that take.");
        return;
      }
    }
    setPhase("error");
    setMessage("Analysis is taking longer than expected. Check back on this recording shortly.");
  }

  async function finish() {
    if (!sessionId) return;
    await api.endSession(sessionId, sessionSeconds.current);
    setSessionId(null);
    sessionSeconds.current = 0;
    setMessage("Session saved to your log.");
  }

  const section = piece?.sections.find((s) => s.id === sectionId);

  return (
    <div className="reveal">
      <p className="eyebrow">
        {piece?.title ?? "Practice"}
        {section && ` · bars ${section.start_bar}–${section.end_bar}`}
      </p>

      <p className="clock display">
        {phase === "recording" && <span className="pulse" />}
        {clock(elapsed)}
      </p>

      <div style={{ display: "flex", gap: 12, marginTop: 32, flexWrap: "wrap" }}>
        {phase === "recording" ? (
          <button type="button" className="btn" onClick={stop}>
            <Icon name="stop" /> Stop
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void start()}
            disabled={phase === "uploading" || phase === "analyzing"}
          >
            <Icon name="record" /> {feedback ? "Another take" : "Record"}
          </button>
        )}
        {sessionId && phase !== "recording" && (
          <button type="button" className="btn btn-quiet" onClick={() => void finish()}>
            End session
          </button>
        )}
      </div>

      {(phase === "uploading" || phase === "analyzing") && (
        <p className="small muted" style={{ marginTop: 24 }}>
          {phase === "uploading" ? "Uploading the take…" : "Listening back…"}
        </p>
      )}

      {message && (
        <p className="notice" data-tone={phase === "error" ? "bad" : undefined} style={{ marginTop: 24 }}>
          {message}
        </p>
      )}

      {piece && piece.sections.length > 0 && phase !== "recording" && (
        <>
          <hr className="rule" />
          <p className="eyebrow">Section</p>
          <div className="sections">
            <button
              type="button"
              className="section-chip"
              aria-pressed={sectionId === null}
              onClick={() => setSectionId(null)}
            >
              whole piece
            </button>
            {piece.sections.map((s) => (
              <button
                type="button"
                key={s.id}
                className="section-chip"
                aria-pressed={sectionId === s.id}
                onClick={() => setSectionId(s.id)}
              >
                {s.start_bar}–{s.end_bar}
              </button>
            ))}
          </div>
        </>
      )}

      {feedback && <Verdict feedback={feedback} playback={playback} />}
    </div>
  );
}

function Verdict({ feedback, playback }: { feedback: Feedback; playback: string | null }) {
  return (
    <div className="reveal">
      <hr className="rule" />
      <p className="eyebrow">That take</p>

      <dl className="readout">
        <Gauge label="Pitch" value={feedback.pitch_accuracy} />
        <Gauge label="Timing" value={feedback.timing_accuracy} />
        <div>
          <dt>Tempo</dt>
          <dd>
            {feedback.tempo_bpm_detected ? Math.round(feedback.tempo_bpm_detected) : "—"}
            <span>bpm</span>
          </dd>
        </div>
        <div>
          <dt>Notes</dt>
          <dd>{feedback.notes_played}</dd>
        </div>
      </dl>

      {feedback.problem_bars.length > 0 && (
        <div style={{ marginTop: 28 }}>
          <p className="eyebrow">Worth another pass</p>
          <div className="bars">
            {feedback.problem_bars.map((bar) => (
              <span className="bar-chip" key={bar}>
                {bar}
              </span>
            ))}
          </div>
        </div>
      )}

      {playback && (
        <audio controls src={playback} style={{ marginTop: 28, width: "100%", maxWidth: 440 }} />
      )}

      <p className="small muted mono" style={{ marginTop: 24 }}>
        {feedback.engine} engine
      </p>
    </div>
  );
}

function Gauge({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        {percent(value)}
        <span>%</span>
      </dd>
      <div className="gauge">
        <span style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
    </div>
  );
}
