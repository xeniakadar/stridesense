"use client";

import { CoachChat } from "@/components/CoachChat";

export default function AskPage() {
  return (
    <div className="coach-page">
      <h1 className="shrink-0 text-[32px] font-medium text-ink leading-tight px-1 pb-1">
        Coach
      </h1>
      <CoachChat />
    </div>
  );
}
