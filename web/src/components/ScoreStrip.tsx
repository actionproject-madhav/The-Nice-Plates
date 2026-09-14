/**
 * A run of bars, drawn as a strip of the score.
 *
 * Bar numbers are a position on a line, not a list of pills: the strip keeps
 * the bars in order and to scale, so "the trouble is all in the second half"
 * is something you see rather than something you work out. The staff lines are
 * a repeating gradient, which keeps them at exactly one device pixel however
 * wide the strip gets.
 *
 * Vermillion means one thing here and everywhere else: this bar needs work.
 */

type Props = {
  from: number;
  to: number;
  problem?: number[];
  /** Bars covered by the current selection, drawn at full ink. */
  active?: [number, number] | null;
  onPick?: (bar: number) => void;
  label?: string;
};

export function ScoreStrip({ from, to, problem = [], active = null, onPick, label }: Props) {
  const bad = new Set(problem);
  const lo = Math.min(from, ...problem.length ? problem : [from]);
  const hi = Math.max(to, ...problem.length ? problem : [to]);
  const bars = Array.from({ length: Math.max(1, hi - lo + 1) }, (_, i) => lo + i);

  // Enough numbers to navigate by, never so many they become a caption.
  const step = bars.length <= 8 ? 1 : bars.length <= 24 ? 4 : bars.length <= 64 ? 8 : 16;
  const numbered = (bar: number) => bad.has(bar) || (bar - lo) % step === 0 || bar === hi;

  return (
    <div
      className="score-strip"
      style={{ ["--bars" as string]: bars.length }}
      role="group"
      aria-label={label ?? `Bars ${lo} to ${hi}`}
    >
      <div className="score-strip-bars">
        {bars.map((bar) => {
          const inside = active ? bar >= active[0] && bar <= active[1] : false;
          const cell = (
            <>
              {bad.has(bar) && <i className="score-strip-mark" />}
              <span className="visually-hidden">
                bar {bar}
                {bad.has(bar) ? ", needs another pass" : ""}
              </span>
            </>
          );
          return onPick ? (
            <button
              type="button"
              key={bar}
              className="score-strip-bar"
              data-bad={bad.has(bar) || undefined}
              data-on={inside || undefined}
              onClick={() => onPick(bar)}
            >
              {cell}
            </button>
          ) : (
            <div
              key={bar}
              className="score-strip-bar"
              data-bad={bad.has(bar) || undefined}
              data-on={inside || undefined}
            >
              {cell}
            </div>
          );
        })}
      </div>
      <div className="score-strip-nums" aria-hidden="true">
        {bars.map((bar) => (
          <span key={bar} data-bad={bad.has(bar) || undefined}>
            {numbered(bar) ? bar : ""}
          </span>
        ))}
      </div>
    </div>
  );
}
