/**
 * Input level while a take is running.
 *
 * A rolling history of RMS level, newest at the right, drawn in the same
 * vocabulary as the ledger and the landing-page waveform: thin vertical rules
 * on a hairline baseline. At rest it is that baseline and nothing else, so the
 * page does not reflow when recording starts — it just comes alive.
 *
 * The rules are written straight to the DOM in the animation frame rather than
 * through React state: ninety-six attribute writes at thirty frames a second
 * are cheap, ninety-six re-renders are not.
 */

import { useEffect, useRef } from "react";

const COLUMNS = 96;
const PITCH = 3;
const MID = 28;
const REACH = 25;

function paint(rects: (SVGRectElement | null)[], levels: number[]) {
  for (let i = 0; i < COLUMNS; i++) {
    const el = rects[i];
    if (!el) continue;
    const h = Math.max(0.35, levels[i] * REACH);
    el.setAttribute("y", String(MID - h));
    el.setAttribute("height", String(h * 2));
  }
}

export function LiveLevel({ stream }: { stream: MediaStream | null }) {
  const rects = useRef<(SVGRectElement | null)[]>([]);
  const levels = useRef<number[]>(new Array(COLUMNS).fill(0));

  useEffect(() => {
    if (!stream) {
      levels.current = new Array(COLUMNS).fill(0);
      paint(rects.current, levels.current);
      return;
    }

    const audio = new AudioContext();
    const source = audio.createMediaStreamSource(stream);
    const analyser = audio.createAnalyser();
    analyser.fftSize = 1024;
    analyser.smoothingTimeConstant = 0.45;
    source.connect(analyser);

    const samples = new Uint8Array(new ArrayBuffer(analyser.fftSize));
    let raf = 0;
    let frame = 0;

    const tick = () => {
      raf = requestAnimationFrame(tick);
      frame += 1;
      if (frame % 2) return;

      analyser.getByteTimeDomainData(samples);
      let sum = 0;
      for (let i = 0; i < samples.length; i++) {
        const v = (samples[i] - 128) / 128;
        sum += v * v;
      }
      // Root mean square, lifted so ordinary playing uses most of the height.
      const rms = Math.min(1, Math.sqrt(sum / samples.length) * 3.4);
      levels.current.push(rms);
      levels.current.shift();
      paint(rects.current, levels.current);
    };

    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      source.disconnect();
      void audio.close();
    };
  }, [stream]);

  return (
    <svg
      className="level"
      viewBox={`0 0 ${COLUMNS * PITCH} ${MID * 2}`}
      preserveAspectRatio="none"
      aria-hidden="true"
      focusable="false"
    >
      <line className="level-base" x1="0" y1={MID} x2={COLUMNS * PITCH} y2={MID} />
      <g className="level-rules" data-live={stream ? "true" : "false"}>
        {Array.from({ length: COLUMNS }, (_, i) => (
          <rect
            key={i}
            ref={(el) => {
              rects.current[i] = el;
            }}
            x={i * PITCH + 0.7}
            y={MID - 0.35}
            width="1.6"
            height="0.7"
          />
        ))}
      </g>
    </svg>
  );
}
