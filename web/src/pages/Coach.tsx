/** The coach. A plain transcript; the tool trace is shown because it's the
 *  evidence that the answer came from this musician's own data. */

import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { api } from "../lib/api";
import { Icon } from "../components/Icon";

interface Turn {
  role: "user" | "assistant";
  content: string;
  tools?: string[];
}

const OPENERS = [
  "How consistent have I been this month?",
  "What should I work on next?",
  "Where am I losing time?",
];

export function Coach() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [threadId, setThreadId] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;

    setTurns((prev) => [...prev, { role: "user", content: message }]);
    setDraft("");
    setBusy(true);
    setError(null);
    try {
      const reply = await api.askCoach(message, threadId);
      setThreadId(reply.thread_id);
      setTurns((prev) => [
        ...prev,
        { role: "assistant", content: reply.reply, tools: reply.tools_used },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The coach didn't answer.");
    } finally {
      setBusy(false);
      box.current?.focus();
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(draft);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(draft);
    }
  }

  return (
    <div className="reveal">
      <p className="eyebrow">Coach</p>
      <h1 className="display title" style={{ marginBottom: 28 }}>
        {turns.length ? " " : "Ask about your own playing."}
      </h1>

      {turns.length === 0 && (
        <>
          <div className="prompts">
            {OPENERS.map((opener) => (
              <button
                type="button"
                key={opener}
                className="section-chip"
                onClick={() => void send(opener)}
              >
                {opener}
              </button>
            ))}
          </div>
        </>
      )}

      <div className="thread">
        {turns.map((turn, i) => (
          <div className="turn" data-role={turn.role} key={i}>
            <div className="turn-body">{turn.content}</div>
            {turn.tools && turn.tools.length > 0 && (
              <p className="tool-trace">read: {[...new Set(turn.tools)].join(", ")}</p>
            )}
          </div>
        ))}
        {busy && <p className="small muted">Reading your log…</p>}
      </div>

      {error && <p className="notice" data-tone="bad">{error}</p>}

      <form className="composer" onSubmit={onSubmit}>
        <textarea
          ref={box}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask something…"
          rows={1}
        />
        <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !draft.trim()}>
          <Icon name="arrow" />
        </button>
      </form>
    </div>
  );
}
