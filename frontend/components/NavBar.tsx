"use client";

import { Plus, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function NavBar() {
  // On the homepage the bar floats transparent over the full-bleed hero
  // mesh and scrolls away with it; everywhere else it's the sticky
  // near-white bar.
  const onHome = usePathname() === "/";

  return (
    <header
      className={
        onHome
          ? "absolute top-0 inset-x-0 z-20"
          : "sticky top-0 z-20 bg-cream/90 backdrop-blur-sm"
      }
    >
      {/* No wordmark up top — the bar is just the actions, pushed clear
          of the iPhone status bar / notch by the safe-area inset */}
      <div className="max-w-md mx-auto px-4 py-3 pt-[calc(0.75rem+env(safe-area-inset-top))] flex items-center justify-end">
        {/* Settings and add-run stay visible in demo as a showcase; the
            pages themselves neutralize any state-changing action. */}
        <nav className="flex items-center gap-1.5">
          <Link
            href="/settings"
            aria-label="Settings"
            className="tap-target p-2 rounded-full text-clay hover:bg-line/60"
          >
            <Settings size={17} strokeWidth={1.75} />
          </Link>
          <Link
            href="/runs/new"
            aria-label="Add run"
            className="tap-target p-2 rounded-full bg-leaf-deep text-white hover:bg-leaf"
          >
            <Plus size={16} strokeWidth={2} />
          </Link>
        </nav>
      </div>
    </header>
  );
}
