/**
 * The first screen, before there is anything to log.
 *
 * An empty dashboard is the one screen every musician sees first and the one
 * with the least to show, so it carries the drawing instead of a paragraph
 * about what the app does. The hero score plays once; the strip below it is
 * the three moves of the product, each one a picture with a two-word caption
 * rather than a sentence.
 *
 * All of it disappears the moment there is a single session to draw.
 */

import type { ReactNode } from "react";
import { ChunkDiagram, TakeDiagram, CoachDiagram, HeroScore } from "./Notation";

const STEPS = [
  { n: "01", label: "Chunk it", figure: <ChunkDiagram /> },
  { n: "02", label: "Record it", figure: <TakeDiagram /> },
  { n: "03", label: "Ask about it", figure: <CoachDiagram /> },
];

export function Overture({ action }: { action?: ReactNode }) {
  return (
    <>
      <HeroScore />
      {action && <div className="actions">{action}</div>}
      <div className="strip">
        {STEPS.map((step) => (
          <figure key={step.n}>
            {step.figure}
            <figcaption>
              <b>{step.n}</b>
              {step.label}
            </figcaption>
          </figure>
        ))}
      </div>
    </>
  );
}
