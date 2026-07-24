"use client";

import { ACWR_EXPLAINER } from "@/lib/acwr";

/** The one plain-language ACWR explainer, shared by the Home load pill
 * and the Trends training-load card so the wording never drifts. */
export function AcwrExplainerPanel({ className = "" }: { className?: string }) {
  return (
    <div
      className={`bg-white/85 border-[0.5px] border-line rounded-xl px-3 py-2.5 text-[12px] leading-relaxed text-clay ${className}`}
    >
      {ACWR_EXPLAINER}
    </div>
  );
}
