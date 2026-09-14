/** One piece: its sections, and the way into practice mode. */

import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type PieceDetail } from "../lib/api";
import { Icon } from "../components/Icon";
import { SectionStrip } from "../components/SectionStrip";

export function PiecePage() {
  const { pieceId = "" } = useParams();
  const navigate = useNavigate();
  const [piece, setPiece] = useState<PieceDetail | null>(null);
  const [totalBars, setTotalBars] = useState(32);
  const [perSection, setPerSection] = useState(4);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getPiece(pieceId).then(setPiece).catch((e) => setError(e.message));
  }, [pieceId]);

  async function chunk() {
    setBusy(true);
    setError(null);
    try {
      const sections = await api.chunkPiece(pieceId, totalBars, perSection);
      setPiece((prev) => (prev ? { ...prev, sections } : prev));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't split that up.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    await api.deletePiece(pieceId);
    navigate("/library");
  }

  if (error) return <p className="notice" data-tone="bad">{error}</p>;
  if (!piece) return <p className="muted">Loading…</p>;

  return (
    <div className="reveal">
      <p className="eyebrow">
        <Link to="/library" className="muted">Library</Link> · {piece.composer ?? "Unattributed"}
      </p>
      <div style={{ display: "flex", alignItems: "baseline", gap: 20, flexWrap: "wrap" }}>
        <h1 className="display title" style={{ flex: 1 }}>{piece.title}</h1>
        <Link to={`/practice/${piece.id}`} className="btn btn-primary">
          <Icon name="record" /> Practise
        </Link>
      </div>

      {piece.tempo_bpm && (
        <p className="small muted mono" style={{ marginTop: 10 }}>{piece.tempo_bpm} bpm</p>
      )}

      <hr className="rule" />

      <p className="eyebrow">Sections</p>
      {piece.sections.length === 0 ? (
        <>
          <div className="row" style={{ maxWidth: 440 }}>
            <label className="field">
              <span>Bars in the piece</span>
              <input
                type="number"
                min={1}
                max={2000}
                value={totalBars}
                onChange={(e) => setTotalBars(Number(e.target.value))}
              />
            </label>
            <label className="field">
              <span>Bars per section</span>
              <input
                type="number"
                min={1}
                max={32}
                value={perSection}
                onChange={(e) => setPerSection(Number(e.target.value))}
              />
            </label>
          </div>
          <button type="button" className="btn btn-primary" onClick={() => void chunk()} disabled={busy}>
            {busy ? "Splitting…" : `Split into ${Math.ceil(totalBars / perSection)} sections`}
          </button>
        </>
      ) : (
        <>
          <SectionStrip
            sections={piece.sections}
            linkTo={(section) => `/practice/${piece.id}?section=${section.id}`}
          />
          <button
            type="button"
            className="btn btn-quiet btn-sm"
            style={{ marginTop: 28 }}
            onClick={() => void chunk()}
            disabled={busy}
          >
            Re-split
          </button>
        </>
      )}

      <hr className="rule" />
      <button type="button" className="btn btn-quiet btn-sm" onClick={() => void remove()}>
        Delete this piece
      </button>
    </div>
  );
}
