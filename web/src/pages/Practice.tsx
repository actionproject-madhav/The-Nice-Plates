/**
 * Practice mode.
 *
 * The one page that exercises the whole pipeline: start a session, record with
 * MediaRecorder, PUT the blob straight to storage, then poll until the worker
 * has something to say.
 *
 * Two kinds of recording go through the same path but land in different
 * analysers — a performance goes to the note transcriber, a spoken note goes to
 * Whisper. Which one is decided here, at record time, because the audio itself
 * doesn't say.
 */

import { useRef, useState, useEffect } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import {
  api,
  putToStorage,
  type Feedback,
  type PieceDetail,
  type RecordingKind,
} from "../lib/api";
import { Icon } from "../components/Icon";
import { LiveLevel } from "../components/LiveLevel";
import { ScoreStrip } from "../components/ScoreStrip";
import { SectionStrip } from "../components/SectionStrip";
import { clock, percent } from "../lib/format";

type Phase = "idle" | "recording" | "uploading" | "analyzing" | "done" | "error";

export function Practice() {
  const { pieceId = "" } = useParams();
  const [params] = useSearchParams();

  const [piece, setPiece] = useState<PieceDetail | null>(null);
  const [sectionId, setSectionId] = useState<string | null>(params.get("section"));
  const [sessionId, setSessionId] = useState<string | null>(null);

  const [phase, setPhase] = useState<Phase>("idle");
  // Held in state, not just on the recorder, so the level meter can read it.
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [kind, setKind] = useState<RecordingKind>("performance");
  const [elapsed, setElapsed] = useState(0);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [transcript, setTranscript] = useState<string | null>(null);
  // What the finished recording was, straight from the API rather than from
  // what we asked for — a voice note has no feedback to render, so its result
  // block has to exist on its own.
  const [done, setDone] = useState<RecordingKind | null>(null);
  const [playback, setPlayback] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const ticker = useRef<number | null>(null);
  const sessionSeconds = useRef(0);
  // Read inside onstop, which closes over the value at record time.
  const recordingKind = useRef<RecordingKind>("performance");
  const recordedSeconds = useRef(0);

  useEffect(() => {
    api.getPiece(pieceId).then(setPiece).catch((e) => setMessage(e.message));
  }, [pieceId]);

  useEffect(
    () => () => {
      if (ticker.current) window.clearInterval(ticker.current);
      recorder.current?.stream.getTracks().forEach((t) => t.stop());
    },
    [],
  );

  async function start(nextKind: RecordingKind) {
    setMessage(null);
    setFeedback(null);
    setTranscript(null);
    setPlayback(null);
    setDone(null);
    setKind(nextKind);
    recordingKind.current = nextKind;

    try {
      const live = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";
      const rec = new MediaRecorder(live, { mimeType: mime });
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
      setStream(live);
      setPhase("recording");
      setElapsed(0);
      recordedSeconds.current = 0;
      ticker.current = window.setInterval(() => {
        recordedSeconds.current += 1;
        sessionSeconds.current += 1;
        setElapsed(recordedSeconds.current);
      }, 1000);
    } catch (e) {
      setStream(null);
      setPhase("error");
      setMessage(
        e instanceof DOMException
          ? "Allow microphone access to record."
          : e instanceof Error
            ? e.message
            : "Couldn't start recording.",
      );
    }
  }

  function stop() {
    if (ticker.current) window.clearInterval(ticker.current);
    recorder.current?.stop();
    recorder.current?.stream.getTracks().forEach((t) => t.stop());
    setStream(null);
    setPhase("uploading");
  }

  async function upload(blob: Blob, mime: string) {
    const isVoice = recordingKind.current === "voice_note";
    try {
      const ticket = await api.uploadUrl({
        filename: `${isVoice ? "note" : "take"}.${mime.includes("mp4") ? "m4a" : "webm"}`,
        content_type: mime,
        kind: recordingKind.current,
        session_id: sessionId ?? undefined,
        piece_id: pieceId,
        section_id: isVoice ? undefined : (sectionId ?? undefined),
      });
      await putToStorage(ticket, blob);
      await api.completeUpload(ticket.recording_id, blob.size, recordedSeconds.current);
      setPhase("analyzing");
      await poll(ticket.recording_id);
    } catch (e) {
      setPhase("error");
      setMessage(e instanceof Error ? e.message : "That recording didn't upload.");
    }
  }

  async function poll(recordingId: string) {
    const deadline = Date.now() + 90_000;
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 1500));
      const status = await api.recording(recordingId);
      if (status.status === "analyzed") {
        setFeedback(status.feedback);
        setTranscript(status.transcript);
        setPlayback(status.playback_url);
        setDone(status.kind);
        setPhase("done");
        return;
      }
      if (status.status === "failed") {
        setPhase("error");
        setMessage(status.error ?? "Couldn’t analyse that take.");
        return;
      }
    }
    setPhase("error");
    setMessage("Still working on it. Check back shortly.");
  }

  async function finish() {
    if (!sessionId) return;
    await api.endSession(sessionId, sessionSeconds.current);
    setSessionId(null);
    sessionSeconds.current = 0;
    setMessage("Saved to your log.");
  }

  const section = piece?.sections.find((s) => s.id === sectionId);
  const lastBar = piece?.sections.reduce((m, s) => Math.max(m, s.end_bar), 0) || 8;
  const working = phase === "uploading" || phase === "analyzing";

  return (
    <div className="reveal">
      <p className="eyebrow">
        {piece?.title ?? "Practice"}
        {section && ` · bars ${section.start_bar}–${section.end_bar}`}
      </p>

      <div className="take">
        <p className="clock display" style={{ margin: 0 }}>
          {phase === "recording" && <span className="pulse" />}
          {clock(elapsed)}
        </p>
        <LiveLevel stream={stream} />
      </div>

      {phase === "recording" && (
        <p className="small muted" style={{ marginTop: 10 }}>
          {kind === "voice_note" ? "Speaking" : "Playing"}
        </p>
      )}

      <div style={{ display: "flex", gap: 12, marginTop: 32, flexWrap: "wrap" }}>
        {phase === "recording" ? (
          <button type="button" className="btn" onClick={stop}>
            <Icon name="stop" /> Stop
          </button>
        ) : (
          <>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void start("performance")}
              disabled={working}
            >
              <Icon name="record" /> {feedback ? "Another take" : "Record"}
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => void start("voice_note")}
              disabled={working}
            >
              <Icon name="mic" /> Voice note
            </button>
          </>
        )}
        {sessionId && phase !== "recording" && (
          <button type="button" className="btn btn-quiet" onClick={() => void finish()}>
            End session
          </button>
        )}
      </div>

      {working && (
        <p className="small muted" style={{ marginTop: 24 }}>
          {phase === "uploading"
            ? "Uploading…"
            : kind === "voice_note"
              ? "Writing it down…"
              : "Listening back…"}
        </p>
      )}

      {message && (
        <p
          className="notice"
          data-tone={phase === "error" ? "bad" : undefined}
          style={{ marginTop: 24 }}
        >
          {message}
        </p>
      )}

      {done === "voice_note" && (
        <div className="reveal" style={{ marginTop: 34 }}>
          <p className="eyebrow">You said</p>
          {transcript ? (
            <blockquote className="said">{transcript}</blockquote>
          ) : (
            <p className="notice">Saved. Nothing came back from transcription.</p>
          )}
          {playback && <audio className="player" controls src={playback} />}
        </div>
      )}

      {piece && piece.sections.length > 0 && phase !== "recording" && (
        <>
          <hr className="rule" />
          <p className="eyebrow">Section</p>
          <SectionStrip
            sections={piece.sections}
            activeId={sectionId}
            onPick={(id) => setSectionId(id === sectionId ? null : id)}
            lead={
              <button
                type="button"
                className="section-chip"
                aria-pressed={sectionId === null}
                onClick={() => setSectionId(null)}
              >
                whole piece
              </button>
            }
          />
        </>
      )}

      {feedback && (
        <Verdict
          feedback={feedback}
          playback={playback}
          from={section?.start_bar ?? 1}
          to={section?.end_bar ?? lastBar}
        />
      )}
    </div>
  );
}

function Verdict({
  feedback,
  playback,
  from,
  to,
}: {
  feedback: Feedback;
  playback: string | null;
  from: number;
  to: number;
}) {
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
        <div style={{ marginTop: 30 }}>
          <p className="eyebrow">Worth another pass</p>
          <ScoreStrip
            from={from}
            to={to}
            problem={feedback.problem_bars}
            label={`Bars that need another pass: ${feedback.problem_bars.join(", ")}`}
          />
        </div>
      )}

      {playback && <audio className="player" controls src={playback} />}

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
