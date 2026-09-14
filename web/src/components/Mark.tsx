/**
 * The mark: an opening repeat sign on a stave.
 *
 * A repeat is the one piece of notation that means "go back and play it
 * again", which is the whole activity this app logs — and the two dots read as
 * a pair of plates, which is the name. Six shapes, no curves but the dots, so
 * it survives a 16px favicon; the thick-thin barline pair and the hairline
 * staff are the same ink-on-paper geometry as everything else drawn here.
 */

export function Mark({ size = 22 }: { size?: number }) {
  return (
    <svg
      className="mark"
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      <g className="mark-staff"><rect x="3.4" y="4.6" width="25.2" height="1.3"/><rect x="3.4" y="26.1" width="25.2" height="1.3"/></g>
      <rect x="9" y="4.6" width="3.6" height="22.8"/>
      <rect x="14.8" y="4.6" width="1.7" height="22.8"/>
      <circle cx="21.8" cy="11.8" r="2.6"/>
      <circle cx="21.8" cy="20.2" r="2.6"/>
    </svg>
  );
}
