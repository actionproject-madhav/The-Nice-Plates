/**
 * Authored musical notation, drawn as inline SVG.
 *
 * Everything here shares one geometry so the panels line up across a row: a
 * 200×96 viewBox, five staff lines at 7-unit spacing centred on y=44, and bar
 * lines at sixths. Because each drawing bleeds to its own viewBox edges, three
 * of them sitting side by side read as one continuous score cut by the panel
 * dividers rather than as three separate cards.
 *
 * Ink only. The single exception is vermillion, which is a data semantic here
 * exactly as it is everywhere else in the app: it means "this bar needs work".
 */

/** Staff-line y positions, top line first. */
const LINES = [30, 37, 44, 51, 58];
/** Seven bar-line x positions across the full width. */
const BARS = [0, 33.33, 66.67, 100, 133.33, 166.67, 200];

const NOTE_RX = 3.3;
const NOTE_RY = 2.5;

function Staff({ faint = false }: { faint?: boolean }) {
  return (
    <g className={faint ? "n-staff n-faint" : "n-staff"}>
      {LINES.map((y) => (
        <line key={y} x1="0" y1={y} x2="200" y2={y} />
      ))}
    </g>
  );
}

function BarLines({ heavyLast = true }: { heavyLast?: boolean }) {
  return (
    <g className="n-bar">
      {BARS.slice(1, -1).map((x) => (
        <line key={x} x1={x} y1="30" x2={x} y2="58" />
      ))}
      {heavyLast && (
        <>
          <line x1="196.4" y1="30" x2="196.4" y2="58" />
          <line className="n-bar-thick" x1="198.8" y1="30" x2="198.8" y2="58" />
        </>
      )}
    </g>
  );
}

/** One notehead with a stem. Beams are drawn separately by the caller. */
function Note({ x, y, stem = 14 }: { x: number; y: number; stem?: number }) {
  return (
    <g>
      <ellipse
        cx={x}
        cy={y}
        rx={NOTE_RX}
        ry={NOTE_RY}
        transform={`rotate(-18 ${x} ${y})`}
        className="n-head"
      />
      {stem > 0 && <line className="n-stem" x1={x + 3.1} y1={y - 0.9} x2={x + 3.1} y2={y - stem} />}
    </g>
  );
}

function Beam({ x1, y1, x2, y2 }: { x1: number; y1: number; x2: number; y2: number }) {
  return (
    <path className="n-beam" d={`M${x1 + 2.9} ${y1} L${x2 + 3.3} ${y2} L${x2 + 3.3} ${y2 + 2.3} L${x1 + 2.9} ${y1 + 2.3} Z`} />
  );
}

function Figure({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <svg className="notation" viewBox="0 0 200 96" role="img" aria-label={label}>
      {children}
    </svg>
  );
}

/* ── 01 · Chunk it ─────────────────────────────────────────────────────────
   Six bars; two of them shaded and at full ink weight. The rest of the score
   steps back. That is what picking a section actually feels like.            */

export function ChunkDiagram() {
  return (
    <Figure label="A score of six bars with a two-bar run picked out for drilling.">
      <rect className="n-span" x={BARS[2]} y="25" width={BARS[4] - BARS[2]} height="38" />
      <Staff />
      <BarLines />
      <g className="n-dim">
        <Note x={12} y={51} />
        <Note x={24} y={44} />
        <Note x={45} y={47.5} />
        <Note x={57} y={40.5} />
        <Note x={145} y={51} />
        <Note x={157} y={44} />
        <Note x={178} y={47.5} />
      </g>
      <g>
        <Note x={76} y={44} stem={15} />
        <Note x={88} y={37} stem={15} />
        <Beam x1={76} y1={29} x2={88} y2={22} />
        <Note x={110} y={40.5} stem={15} />
        <Note x={122} y={47.5} stem={15} />
        <Beam x1={110} y1={25.5} x2={122} y2={32.5} />
      </g>
      <path className="n-brace" d={`M${BARS[2]} 68 v4 H${BARS[4]} v-4`} />
    </Figure>
  );
}

/* ── 02 · Record it ────────────────────────────────────────────────────────
   The same staff, with a take laid over it. The waveform overruns the stave
   because that is the honest picture: audio is not notation yet.             */

const SAMPLES = 48;
const WAVE = Array.from({ length: SAMPLES }, (_, i) => {
  const t = i / (SAMPLES - 1);
  const envelope = Math.sin(Math.PI * t) ** 0.55;
  const detail = 0.3 + 0.7 * Math.abs(Math.sin(i * 1.71) * Math.cos(i * 0.63) + 0.25 * Math.sin(i * 0.31));
  return 1.6 + envelope * detail * 21;
});

export function TakeDiagram() {
  return (
    <Figure label="A recorded take drawn as a waveform across the stave.">
      <Staff faint />
      <g className="n-wave">
        {WAVE.map((h, i) => {
          const x = 3 + (i * 194) / (SAMPLES - 1);
          return <line key={i} x1={x} y1={44 - h} x2={x} y2={44 + h} />;
        })}
      </g>
      <path className="n-brace" d="M3 74 v4 H197 v-4" />
    </Figure>
  );
}

/* ── 03 · Ask about it ─────────────────────────────────────────────────────
   Three takes of the same six bars, stacked oldest to newest. One column
   keeps coming back marked. The ring on the stave says which notes those are. */

const TAKES = [
  [0, 1, 0, 0, 1, 0],
  [0, 0, 0, 0, 1, 0],
  [0, 1, 0, 0, 1, 0],
];

export function CoachDiagram() {
  const cellW = (BARS[1] - BARS[0]) - 3;
  return (
    <Figure label="Three takes of the same six bars, with one bar marked in every take.">
      <Staff faint />
      <BarLines heavyLast={false} />
      <g className="n-dim">
        <Note x={12} y={51} />
        <Note x={24} y={44} />
        <Note x={45} y={47.5} />
        <Note x={57} y={40.5} />
        <Note x={78} y={44} />
        <Note x={90} y={37} />
        <Note x={111} y={40.5} />
        <Note x={123} y={47.5} />
        <Note x={178} y={51} />
      </g>
      <g className="n-flag">
        <Note x={145} y={47.5} />
        <Note x={157} y={40.5} />
        <ellipse className="n-ring" cx={151} cy={44} rx={13} ry={8.5} />
      </g>
      <g>
        {TAKES.map((row, r) =>
          row.map((bad, c) => (
            <rect
              key={`${r}-${c}`}
              className={bad ? "n-cell n-cell-bad" : "n-cell"}
              x={BARS[c] + 1.5}
              y={68 + r * 6}
              width={cellW}
              height="4"
              rx="1"
            />
          )),
        )}
      </g>
    </Figure>
  );
}
