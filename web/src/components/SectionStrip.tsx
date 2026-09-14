/**
 * A piece's sections, drawn as the score they came from.
 *
 * Sections are bar ranges, so they belong on a line in order and to scale, not
 * in a wrapping row of pills where bars 1–4 and bars 69–72 look identical and
 * a long section looks the same as a short one. Each section is one cell of a
 * grid whose column widths are its bar count, over the same staff gradient the
 * feedback strip uses.
 *
 * The readout above behaves like the ledger's: the summary until you point at
 * something, then that thing.
 */

import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { Section } from "../lib/api";

type Props = {
  sections: Section[];
  activeId?: string | null;
  onPick?: (id: string) => void;
  linkTo?: (section: Section) => string;
  /** Left-hand side of the readout row — a "whole piece" toggle, usually. */
  lead?: ReactNode;
};

export function SectionStrip({ sections, activeId, onPick, linkTo, lead }: Props) {
  const [hot, setHot] = useState<string | null>(null);
  if (sections.length === 0) return null;

  const shown = sections.find((s) => s.id === (hot ?? activeId)) ?? null;
  const lastBar = sections[sections.length - 1].end_bar;
  const columns = sections.map((s) => `${Math.max(1, s.end_bar - s.start_bar + 1)}fr`).join(" ");

  // Enough start-bar numbers to navigate by, never a caption.
  const every = sections.length <= 10 ? 1 : sections.length <= 24 ? 3 : 6;

  return (
    <div className="sec" onPointerLeave={() => setHot(null)}>
      <p className="sec-readout">
        <span>{lead}</span>
        <span className="sec-readout-value">
          {shown
            ? `bars ${shown.start_bar}–${shown.end_bar}`
            : `${sections.length} sections · ${lastBar} bars`}
        </span>
      </p>

      <div className="sec-strip" style={{ gridTemplateColumns: columns }}>
        {sections.map((section) => {
          const props = {
            className: "sec-cell",
            "data-on": section.id === activeId || undefined,
            onPointerEnter: () => setHot(section.id),
            // Keyboard focus moves the readout too, or a keyboard user gets
            // an outline and no idea which bars they are on.
            onFocus: () => setHot(section.id),
            onBlur: () => setHot(null),
            children: (
              <span className="visually-hidden">
                bars {section.start_bar} to {section.end_bar}
              </span>
            ),
          };
          return linkTo ? (
            <Link key={section.id} to={linkTo(section)} {...props} />
          ) : (
            <button
              key={section.id}
              type="button"
              aria-pressed={section.id === activeId}
              onClick={() => onPick?.(section.id)}
              {...props}
            />
          );
        })}
      </div>

      <div className="sec-nums" style={{ gridTemplateColumns: columns }} aria-hidden="true">
        {sections.map((section, i) => (
          <span key={section.id} data-on={section.id === activeId || undefined}>
            {i % every === 0 ? section.start_bar : ""}
          </span>
        ))}
      </div>
    </div>
  );
}
