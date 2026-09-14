/** Repertoire. Add a piece, or open one. */

import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, type Piece } from "../lib/api";
import { Icon } from "../components/Icon";
import { BlankStave } from "../components/Notation";
import { relativeDay } from "../lib/format";
import { friendly } from "../lib/errors";

export function Library() {
  const [pieces, setPieces] = useState<Piece[]>([]);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listPieces().then(setPieces).catch((e) => setError(friendly(e, "Couldn’t load your library.")));
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const title = String(form.get("title") ?? "").trim();
    if (!title) return;

    setBusy(true);
    setError(null);
    try {
      const piece = await api.createPiece({
        title,
        composer: String(form.get("composer") ?? "").trim() || undefined,
        tempo_bpm: Number(form.get("tempo")) || undefined,
      });
      setPieces((prev) => [piece, ...prev]);
      setAdding(false);
      event.currentTarget.reset();
    } catch (e) {
      setError(friendly(e, "Couldn’t save that piece."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="reveal">
      <p className="eyebrow">Repertoire</p>
      <div style={{ display: "flex", alignItems: "baseline", gap: 20, flexWrap: "wrap" }}>
        <h1 className="display title" style={{ flex: 1 }}>
          {pieces.length ? `${pieces.length} piece${pieces.length === 1 ? "" : "s"}` : "Library"}
        </h1>
        <button
          type="button"
          className={adding ? "btn btn-quiet" : "btn btn-primary"}
          onClick={() => setAdding((v) => !v)}
        >
          {adding ? "Cancel" : <><Icon name="plus" /> Add a piece</>}
        </button>
      </div>

      {adding && (
        <form className="panel reveal" style={{ marginTop: 28 }} onSubmit={submit}>
          <div className="row">
            <label className="field">
              <span>Title</span>
              <input name="title" required autoFocus placeholder="Gymnopédie No. 1" />
            </label>
            <label className="field">
              <span>Composer</span>
              <input name="composer" placeholder="Satie" />
            </label>
            <label className="field">
              <span>Tempo</span>
              <input name="tempo" type="number" min={20} max={300} placeholder="72" />
            </label>
          </div>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </button>
        </form>
      )}

      {error && <p className="notice" data-tone="bad" style={{ marginTop: 24 }}>{error}</p>}

      <hr className="rule" />

      {pieces.length === 0 ? (
        <div className="blank">
          <BlankStave />
          <p className="eyebrow">Nothing here yet</p>
        </div>
      ) : (
        <div className="stack">
          {pieces.map((piece) => (
            <Link className="entry" key={piece.id} to={`/piece/${piece.id}`}>
              <span className="entry-title">
                {piece.title}
                {piece.composer && <span className="muted small"> · {piece.composer}</span>}
              </span>
              {piece.tempo_bpm && <span className="entry-meta">{piece.tempo_bpm} bpm</span>}
              <span className="entry-meta muted">{relativeDay(piece.updated_at)}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
