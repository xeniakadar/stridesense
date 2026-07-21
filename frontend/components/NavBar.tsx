"use client";

import Link from "next/link";

import { useDemoMode } from "@/components/DemoProvider";

export function NavBar() {
  const demoMode = useDemoMode();

  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-lg font-medium">
            StrideSense
          </Link>
          {demoMode && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200">
              Demo — seeded data
            </span>
          )}
        </div>
        <nav className="flex gap-6 text-sm text-gray-600 items-center">
          <Link href="/" className="hover:text-gray-900">
            Dashboard
          </Link>
          <Link href="/runs" className="hover:text-gray-900">
            Runs
          </Link>
          {!demoMode && (
            <>
              <Link href="/settings" className="hover:text-gray-900">
                Settings
              </Link>
              <Link
                href="/runs/new"
                className="text-white bg-gray-900 hover:bg-gray-700 px-3 py-1.5 rounded"
              >
                + Add run
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
