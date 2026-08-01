"use client";

import { useDemoMode } from "@/components/DemoProvider";
import { Logo } from "@/components/Logo";

/** Info column beside the desktop device frame (hidden below 900px —
 * see the .shell-aside rules in globals.css). Presentation chrome only:
 * it reads demo mode to caption the deployment honestly, nothing else. */
export function PresentationAside() {
  const demoMode = useDemoMode();
  return (
    <aside className="shell-aside">
      <Logo size={24} />
      {demoMode && (
        <p className="mt-3 text-[13px] text-clay">
          Read-only demo · synthetic data
        </p>
      )}
      <a
        href="https://xeniakadar.com/work/stridesense"
        className="mt-2 inline-flex items-center gap-1 text-[13px] font-semibold text-[#0FA98E] hover:underline"
      >
        Read the case study <span aria-hidden>→</span>
      </a>
    </aside>
  );
}
