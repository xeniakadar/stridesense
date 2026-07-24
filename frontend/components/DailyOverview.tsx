"use client";

import { useEffect, useState } from "react";

import { AiText } from "@/components/AiText";
import { api } from "@/lib/api";
import type { DailyBrief } from "@/lib/types";

export function DailyOverview() {
  const [brief, setBrief] = useState<DailyBrief | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    api
      .getDailyBrief()
      .then(setBrief)
      .catch(() => setUnavailable(true));
  }, []);

  return (
    <div className="glass-ai rounded-2xl p-4">
      <h2 className="text-[20px] font-medium text-leaf-deep leading-snug">Daily overview</h2>
      {unavailable ? (
        <p className="mt-2 text-sm text-clay">
          The overview isn't available right now — check back in a bit.
        </p>
      ) : brief ? (
        <AiText text={brief.content} className="mt-2" />
      ) : (
        <p className="mt-2 text-sm text-clay">Reading your morning…</p>
      )}
    </div>
  );
}
