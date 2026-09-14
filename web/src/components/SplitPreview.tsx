/**
 * What splitting is about to do, drawn while you set the numbers.
 *
 * It is the same strip the piece gets afterwards — same staff gradient, same
 * proportional columns — so the control and its result are the same picture,
 * and the preview simply fills with real sections when you commit it.
 */

export function SplitPreview({ totalBars, perSection }: { totalBars: number; perSection: number }) {
  const bars = Math.max(1, Math.min(2000, Math.floor(totalBars) || 1));
  const per = Math.max(1, Math.min(32, Math.floor(perSection) || 1));
  const count = Math.ceil(bars / per);
  const spans = Array.from({ length: count }, (_, i) => Math.min(per, bars - i * per));

  return (
    <div className="sec" aria-hidden="true">
      <p className="sec-readout">
        <span />
        <span className="sec-readout-value">
          {count} section{count === 1 ? "" : "s"} · {bars} bars
        </span>
      </p>
      <div
        className="sec-strip"
        data-preview="true"
        style={{ gridTemplateColumns: spans.map((s) => `${s}fr`).join(" ") }}
      >
        {spans.map((_, i) => (
          <div key={i} className="sec-cell" />
        ))}
      </div>
    </div>
  );
}
