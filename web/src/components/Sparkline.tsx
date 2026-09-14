/**
 * Accuracy across the analysed takes, oldest to newest.
 *
 * A hairline and its last number. No axes: the only two things worth reading
 * are the shape and where it ended up, and both are already on the page.
 */

type Props = { values: number[]; label: string };

const W = 200;
const H = 46;

export function Sparkline({ values, label }: Props) {
  if (values.length < 2) return null;

  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pad = Math.max(0.02, (hi - lo) * 0.25);
  const top = Math.min(1, hi + pad);
  const bottom = Math.max(0, lo - pad);

  const x = (i: number) => (i / (values.length - 1)) * W;
  const y = (v: number) => H - ((v - bottom) / (top - bottom || 1)) * H;
  const path = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const last = values[values.length - 1];

  return (
    <figure className="spark">
      <figcaption className="eyebrow">{label}</figcaption>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${label} across the last ${values.length} analysed takes, now ${Math.round(last * 100)} percent.`}
      >
        <path className="spark-line" d={path} />
        <circle className="spark-end" cx={x(values.length - 1)} cy={y(last)} r="2.6" />
      </svg>
      <p className="spark-value mono">
        {Math.round(last * 100)}
        <span>%</span>
      </p>
    </figure>
  );
}
