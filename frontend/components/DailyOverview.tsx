"use client";

import { useEffect, useState } from "react";

import { AiText } from "@/components/AiText";
import { Glass } from "@/components/Glass";
import { ReadMore } from "@/components/ReadMore";
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
    <Glass variant="brief" className="p-4">
      <h2 className="text-[20px] font-medium glass-header leading-snug">
        Daily overview
      </h2>
      {unavailable ? (
        <p className="mt-2 text-sm text-clay">
          The overview isn't available right now — check back in a bit.
        </p>
      ) : brief ? (
        <ReadMore className="mt-2">
          <AiText text={brief.content} />
        </ReadMore>
      ) : (
        <p className="mt-2 text-sm text-clay">Reading your morning…</p>
      )}
    </Glass>
  );
}
