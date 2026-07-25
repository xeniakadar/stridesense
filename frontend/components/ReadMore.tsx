"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const COLLAPSED_LINES = 5;
// Fallback if line-height can't be measured: 14px text at leading-relaxed
const FALLBACK_LINE_PX = 22.75;

/** Collapse long AI text to ~5 lines with a "Read more" toggle.
 *
 * Uses max-height + overflow (NOT -webkit-line-clamp: the children are
 * react-markdown output with multiple block elements, which line-clamp
 * handles unreliably). The bottom fade is a mask-image on the text
 * itself rather than a color overlay — the glass cards sit on a two-hue
 * gradient over backdrop blur, so no overlay color can match; fading
 * the text out reveals the card's real background, which is invisible
 * against any tint by construction.
 *
 * The toggle renders only when the content actually overflows the
 * collapsed height (measured, re-measured on resize); short content
 * shows uncollapsed with no link. */
export function ReadMore({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [overflows, setOverflows] = useState(false);
  const [collapsedPx, setCollapsedPx] = useState(
    COLLAPSED_LINES * FALLBACK_LINE_PX
  );

  const measure = useCallback(() => {
    const el = contentRef.current;
    if (!el) return;
    // Line-height lives on the AiText child, not this wrapper
    const inner = (el.firstElementChild as HTMLElement | null) ?? el;
    const lh = parseFloat(getComputedStyle(inner).lineHeight) || FALLBACK_LINE_PX;
    const max = COLLAPSED_LINES * lh;
    setCollapsedPx(max);
    // scrollHeight is the full content height regardless of collapse state
    setOverflows(el.scrollHeight > max + 2);
  }, []);

  useEffect(() => {
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [measure, children]);

  const collapsed = overflows && !expanded;

  const toggle = () => {
    if (expanded) {
      setExpanded(false);
      // If expanding pushed the card top offscreen, bring it back so the
      // reader isn't left mid-page after the fold snaps shut
      requestAnimationFrame(() => {
        const wrap = wrapRef.current;
        if (wrap && wrap.getBoundingClientRect().top < 0) {
          wrap.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    } else {
      setExpanded(true);
    }
  };

  const fade = "linear-gradient(to bottom, black calc(100% - 2.5em), transparent)";

  return (
    <div ref={wrapRef} className={`scroll-mt-20 ${className}`}>
      <div
        ref={contentRef}
        style={
          collapsed
            ? {
                maxHeight: collapsedPx,
                overflow: "hidden",
                maskImage: fade,
                WebkitMaskImage: fade,
              }
            : undefined
        }
      >
        {children}
      </div>
      {overflows && (
        <button
          type="button"
          onClick={toggle}
          aria-expanded={expanded}
          className="tap-target mt-1.5 text-[12.5px] font-semibold text-[#0FA98E]"
        >
          {expanded ? "Show less" : "Read more"}
        </button>
      )}
    </div>
  );
}
