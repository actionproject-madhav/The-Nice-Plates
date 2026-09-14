/**
 * The practice ledger.
 *
 * One rule per day, height proportional to minutes practised. Days off are a
 * flat tick, so a gap looks like a gap. No axes, no gridlines, no legend — the
 * silhouette carries the whole story, which is the point.
 *
 * Hovering a day dims the rest and writes that day into the readout above,
 * which otherwise holds the summary. That is one line of type doing the work
 * of an axis, a tooltip and a caption.
 */

import { useState } from "react";
import { fillDays, duration, shortDate } from "../lib/format";
import type { DaySummary } from "../lib/api";

export function Ledger({ days, span = 30 }: { days: DaySummary[]; span?: number }) {
  const series = fillDays(days, span);
  const peak = Math.max(...series.map((d) => d.minutes), 30);
  const today = new Date().toISOString().slice(0, 10);
  const [hot, setHot] = useState<number | null>(null);

  const played = series.filter((d) => d.minutes > 0).length;
  const total = series.reduce((sum, d) => sum + d.minutes, 0);
  const day = hot === null ? null : series[hot];

  return (
    <figure style={{ margin: 0 }}>
      <p className="ledger-readout">
        {day ? (
          <>
            <span className="ledger-readout-date">
              {day.date === today ? "today" : shortDate(day.date)}
            </span>
            {day.minutes ? duration(day.minutes) : "no practice"}
          </>
        ) : (
          <>
            <span className="ledger-readout-date">{played} of {span} days</span>
            {duration(total)}
          </>
        )}
      </p>

      <div
        className="ledger"
        data-focused={hot !== null || undefined}
        role="img"
        aria-label={`Practice over the last ${span} days: ${played} days played, ${total} minutes total.`}
        onPointerLeave={() => setHot(null)}
      >
        {series.map((d, i) => (
          <div
            key={d.date}
            className="ledger-day"
            data-empty={d.minutes === 0 || undefined}
            data-today={d.date === today || undefined}
            data-hot={hot === i || undefined}
            style={{ height: `${Math.max((d.minutes / peak) * 100, 2)}%` }}
            onPointerEnter={() => setHot(i)}
          />
        ))}
      </div>

      <figcaption className="ledger-scale">
        <span>{span} days ago</span>
        <span data-today="true">today</span>
      </figcaption>
    </figure>
  );
}
