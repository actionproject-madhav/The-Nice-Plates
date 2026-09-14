/**
 * Thin-line icons, drawn inline.
 *
 * No icon library and no emoji: a 1.25px stroke at currentColor sits with the
 * hairline rules, and thick-stroke sets read as a different design language.
 */

type Props = { name: IconName; size?: number };
export type IconName = "record" | "stop" | "arrow" | "plus" | "check" | "wave" | "mic";

const paths: Record<IconName, JSX.Element> = {
  record: <circle cx="12" cy="12" r="5.5" />,
  stop: <rect x="7.5" y="7.5" width="9" height="9" rx="1" />,
  arrow: <path d="M4 12h15m0 0-5.5-5.5M19 12l-5.5 5.5" />,
  plus: <path d="M12 5v14M5 12h14" />,
  check: <path d="m5 12.5 4.5 4.5L19 7" />,
  wave: <path d="M3 12h2.5l2-6 3 13 3-16 2.5 9H21" />,
  mic: (
    <>
      <rect x="9.5" y="3" width="5" height="11" rx="2.5" />
      <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" />
    </>
  ),
};

export function Icon({ name, size = 16 }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {paths[name]}
    </svg>
  );
}
