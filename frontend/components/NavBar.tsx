"use client";

import { Plus, Settings } from "lucide-react";
import Link from "next/link";

import { useDemoMode } from "@/components/DemoProvider";

export function NavBar() {
  const demoMode = useDemoMode();

  return (
    <header className="sticky top-0 z-20 bg-cream/90 backdrop-blur-sm">
      <div className="max-w-md mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Link href="/" className="text-base font-medium text-ink">
            StrideSense
          </Link>
          {demoMode && (
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200">
              Demo — seeded data
            </span>
          )}
        </div>
        {!demoMode && (
          <nav className="flex items-center gap-1.5">
            <Link
              href="/settings"
              aria-label="Settings"
              className="p-2 rounded-full text-clay hover:bg-line/60"
            >
              <Settings size={17} strokeWidth={1.75} />
            </Link>
            <Link
              href="/runs/new"
              aria-label="Add run"
              className="p-2 rounded-full bg-ink text-cream hover:bg-clay"
            >
              <Plus size={16} strokeWidth={2} />
            </Link>
          </nav>
        )}
      </div>
    </header>
  );
}
