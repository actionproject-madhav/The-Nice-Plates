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

/* ── The hero score ────────────────────────────────────────────────────────
   One orchestrated moment: a take sweeps in as a waveform, then a phrase of
   notation lands on the stave note by note while the waveform settles back to
   a ghost behind it. That is the whole product in four seconds, shown rather
   than claimed. The staff and bar lines never move — they are the paper.

   Geometry: 640×150, five lines at 11-unit spacing centred on y=77, six bars.
   Step 0 is the bottom line and each step is half a staff space.             */

const H_LINES = [55, 66, 77, 88, 99];
const H_BARW = 640 / 6;
const yOf = (step: number) => 99 - step * 5.5;

type Melody = { bar: number; at: number; step: number };

/** A rising phrase that settles. Beamed runs are marked by BEAMS below. */
const PHRASE: Melody[] = [
  { bar: 0, at: 32, step: 2 },
  { bar: 0, at: 76, step: 4 },
  { bar: 1, at: 20, step: 5 },
  { bar: 1, at: 53, step: 7 },
  { bar: 1, at: 86, step: 8 },
  { bar: 2, at: 30, step: 7 },
  { bar: 2, at: 74, step: 5 },
  { bar: 3, at: 20, step: 6 },
  { bar: 3, at: 53, step: 8 },
  { bar: 3, at: 86, step: 9 },
  { bar: 4, at: 30, step: 7 },
  { bar: 4, at: 74, step: 5 },
  { bar: 5, at: 46, step: 4 },
];
const BEAMS: number[][] = [
  [2, 3, 4],
  [7, 8, 9],
];
const WHOLE = PHRASE.length - 1;

const STEM = 24;
const HERO_WAVE = 240;
const NOTE_DELAY = 70;
const NOTE_START = 950;

function heroX(n: Melody) {
  return n.bar * H_BARW + n.at;
}

function delay(i: number) {
  return { "--d": `${NOTE_START + i * NOTE_DELAY}ms` } as React.CSSProperties;
}

export function HeroScore() {
  const xs = PHRASE.map(heroX);
  const ys = PHRASE.map((n) => yOf(n.step));
  const beamed = new Set(BEAMS.flat());

  return (
    <svg
      className="notation hero-score"
      viewBox="0 20 640 112"
      preserveAspectRatio="xMinYMid slice"
      role="img"
      aria-label="A recorded take drawn as a waveform, resolving into a written phrase of six bars."
    >
      <g className="hero-wave">
        {Array.from({ length: HERO_WAVE }, (_, i) => {
          const t = i / (HERO_WAVE - 1);
          const envelope = Math.sin(Math.PI * t) ** 0.5;
          const detail =
            0.28 +
            0.72 *
              Math.abs(Math.sin(i * 1.63) * Math.cos(i * 0.47) + 0.3 * Math.sin(i * 0.21));
          const h = 1.5 + envelope * detail * 32;
          return (
            <rect
              key={i}
              x={2 + t * 636 - 0.45}
              y={77 - h}
              width="0.9"
              height={h * 2}
              rx="0.45"
              style={{ "--d": `${i * 3}ms` } as React.CSSProperties}
            />
          );
        })}
      </g>

      <g className="n-staff">
        {H_LINES.map((y) => (
          <line key={y} x1="0" y1={y} x2="640" y2={y} />
        ))}
      </g>
      <g className="n-bar">
        {[1, 2, 3, 4, 5].map((b) => (
          <line key={b} x1={b * H_BARW} y1="55" x2={b * H_BARW} y2="99" />
        ))}
        <line x1="635" y1="55" x2="635" y2="99" />
        <line className="n-bar-thick" x1="638.6" y1="55" x2="638.6" y2="99" />
      </g>

      {PHRASE.map((n, i) => {
        const x = xs[i];
        const y = ys[i];
        const down = n.step >= 5;
        return (
          <g className="hero-note" key={i} style={delay(i)}>
            {i === WHOLE ? (
              <ellipse className="n-head-open" cx={x} cy={y} rx="5.4" ry="3.9" transform={`rotate(-14 ${x} ${y})`} />
            ) : (
              <>
                <ellipse className="n-head" cx={x} cy={y} rx="5.2" ry="3.8" transform={`rotate(-18 ${x} ${y})`} />
                {!beamed.has(i) && (
                  <line
                    className="n-stem-h"
                    x1={x + (down ? -3.9 : 3.9)}
                    y1={y + (down ? 1 : -1)}
                    x2={x + (down ? -3.9 : 3.9)}
                    y2={y + (down ? STEM : -STEM)}
                  />
                )}
              </>
            )}
          </g>
        );
      })}

      {BEAMS.map((group) => {
        const down = PHRASE[group[0]].step >= 5;
        const sx = group.map((i) => xs[i] + (down ? -3.9 : 3.9));
        const ends = group.map((i) => ys[i] + (down ? STEM : -STEM));
        const x1 = sx[0];
        const x2 = sx[sx.length - 1];
        // Engravers cap beam slope and never let a stem get shorter than about
        // two staff spaces: clamp the rise, then push the whole beam clear.
        const mid = (ends[0] + ends[ends.length - 1]) / 2;
        const rise = Math.max(-8, Math.min(8, (ends[ends.length - 1] - ends[0]) / 2));
        let a = mid - rise;
        let b = mid + rise;
        const line = (x: number) => a + ((b - a) * (x - x1)) / (x2 - x1);
        const need = Math.max(
          ...group.map((i, k) => (down ? ys[i] + 15 - line(sx[k]) : line(sx[k]) - (ys[i] - 15))),
        );
        if (need > 0) {
          const shift = down ? need : -need;
          a += shift;
          b += shift;
        }
        const at = line;
        const [y1, y2] = [a, b];
        const thick = down ? -3.2 : 3.2;
        return (
          <g className="hero-note" key={group[0]} style={delay(group[group.length - 1])}>
            {group.map((i, k) => (
              <line
                className="n-stem-h"
                key={i}
                x1={sx[k]}
                y1={ys[i] + (down ? 1 : -1)}
                x2={sx[k]}
                y2={at(sx[k])}
              />
            ))}
            <path
              className="n-beam"
              d={`M${x1} ${y1} L${x2} ${y2} L${x2} ${y2 + thick} L${x1} ${y1 + thick} Z`}
            />
          </g>
        );
      })}
    </svg>
  );
}
