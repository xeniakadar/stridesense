"use client";

import { useEffect, useRef, useState } from "react";

// Mesh palette hues (globals.css) — the confetti stays on-brand
const COLORS = ["#FF8A6B", "#FF5E7E", "#FFC46B", "#5FD4BE", "#C8E87A", "#B78BE8"];

const FADE_MS = 600;

/** One celebratory dependency-free confetti burst, rendered to a
 * full-screen canvas that ignores pointer events and unmounts itself
 * when done. Skipped entirely under prefers-reduced-motion. */
export function Confetti({ duration = 2600 }: { duration?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setDone(true);
      return;
    }
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = window.innerWidth;
    const h = window.innerHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    // Pieces rain from just above the viewport with a little sideways drift
    const pieces = Array.from({ length: 140 }, () => ({
      x: Math.random() * w,
      y: -20 - Math.random() * h * 0.35,
      vx: (Math.random() - 0.5) * 2.2,
      vy: 2.2 + Math.random() * 3,
      size: 5 + Math.random() * 5,
      color: COLORS[Math.floor(Math.random() * COLORS.length)],
      rot: Math.random() * Math.PI,
      vr: (Math.random() - 0.5) * 0.25,
      // Phase offset so the flutter (width oscillation) isn't in lockstep
      phase: Math.random() * Math.PI * 2,
    }));

    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = now - start;
      if (t > duration + FADE_MS) {
        setDone(true);
        return;
      }
      ctx.clearRect(0, 0, w, h);
      ctx.globalAlpha =
        t > duration ? Math.max(0, 1 - (t - duration) / FADE_MS) : 1;
      for (const p of pieces) {
        p.x += p.vx;
        p.y += p.vy;
        p.rot += p.vr;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillStyle = p.color;
        // Oscillating width fakes a tumbling rectangle
        const wobble = 0.35 + 0.65 * Math.abs(Math.sin(t / 220 + p.phase));
        ctx.fillRect((-p.size / 2) * wobble, -p.size / 4, p.size * wobble, p.size / 2);
        ctx.restore();
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [duration]);

  if (done) return null;
  return (
    <canvas
      ref={ref}
      className="fixed inset-0 z-50 pointer-events-none"
      aria-hidden
    />
  );
}
