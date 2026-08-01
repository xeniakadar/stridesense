import { Logo } from "@/components/Logo";

/** Info column beside the desktop device frame — just the lockup.
 * Hidden below 900px (see the .shell-aside rules in globals.css). */
export function PresentationAside() {
  return (
    <aside className="shell-aside">
      <Logo size={24} />
      {/* Return link to the portfolio: plain anchor (independent of
          client routing), same tab. Desktop-only by construction — the
          aside never renders below 900px. */}
      <a
        href="https://www.xeniakadar.com/work/stridesense"
        className="mt-6 flex items-center gap-1.5 text-[14px] font-medium text-[#0FA98E] hover:text-[#0C8A74] hover:underline"
      >
        <span aria-hidden>←</span> Back to case study
      </a>
    </aside>
  );
}
