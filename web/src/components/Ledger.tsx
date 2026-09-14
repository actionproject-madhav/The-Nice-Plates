/**
 * The practice ledger.
 *
 * One hairline rule per day, height proportional to minutes practised. Days
 * off are a flat tick, so a gap looks like a gap. No axes, no gridlines, no
 * legend — the silhouette carries the whole story, which is the point.
 */

import { fillDays, minutes as fmtMinutes } from "../lib/format";
import type { DaySummary } from "../lib/api";

export function Ledger({ days, span = 30 }: { days: DaySummary[]; span?: number }) {
  const series = fillDays(days, span);
  const peak = Math.max(...series.map((d) => d.minutes), 30);
  const today = new Date().toISOString().slice(0, 10);

  return (
    <figure style={{ margin: 0 }}>
      <div className="ledger" role="img" aria-label={ariaLabel(series, span)}>
        {series.map((day) => (
          <div
            key={day.date}
            className="ledger-day"
            data-empty={day.minutes === 0}
            data-today={day.date === today}
            style={{ height: `${Math.max((day.minutes / peak) * 100, 2)}%` }}
            title={`${day.date} — ${day.minutes ? `${day.minutes} min` : "no practice"}`}
          />
        ))}
      </div>
      <figcaption className="ledger-scale">
        <span>{span} days ago</span>
        <span className="mono">{fmtMinutes(peak)} min peak</span>
        <span>today</span>
      </figcaption>
    </figure>
  );
}

function ariaLabel(series: { minutes: number }[], span: number): string {
  const active = series.filter((d) => d.minutes > 0).length;
  const total = series.reduce((sum, d) => sum + d.minutes, 0);
  return `Practice over the last ${span} days: ${active} days played, ${total} minutes total.`;
}
