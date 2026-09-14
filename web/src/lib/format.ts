/** Small formatters. Shared so "25 min" never renders three different ways. */

export function duration(total: number): string {
  if (total < 60) return `${total} min`;
  const h = Math.floor(total / 60);
  const m = total % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

export function clock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function percent(value: number): string {
  return `${Math.round(value * 100)}`;
}

export function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function relativeDay(iso: string): string {
  const then = new Date(iso);
  const days = Math.floor((Date.now() - then.getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  return shortDate(iso);
}

/** Backfill a continuous run of days so gaps in practice are visible as gaps. */
export function fillDays(
  days: { date: string; minutes: number }[],
  span: number,
): { date: string; minutes: number }[] {
  const byDate = new Map(days.map((d) => [d.date, d.minutes]));
  const out: { date: string; minutes: number }[] = [];
  const today = new Date();
  for (let i = span - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    out.push({ date: key, minutes: byDate.get(key) ?? 0 });
  }
  return out;
}
