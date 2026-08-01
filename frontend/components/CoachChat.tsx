"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { AiText } from "@/components/AiText";
import { useDemoMode } from "@/components/DemoProvider";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatDistance, RUN_TYPE_LABELS } from "@/lib/format";
import type { AskAnswer } from "@/lib/types";

const STARTER_QUESTIONS = [
  "How do I handle hot weather?",
  "Tell me about my races",
  "How has my pace changed?",
];

/** One question → answer round trip. The transcript is a UI metaphor:
 * every ask is an independent POST (or demo lookup); no history is sent
 * to the backend, and nothing is persisted — refresh starts clean. */
interface Exchange {
  id: number;
  question: string;
  status: "loading" | "done" | "error";
  answer?: AskAnswer;
  error?: string;
}

export function CoachChat() {
  const demoMode = useDemoMode();
  const [demoQuestions, setDemoQuestions] = useState<string[]>([]);
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [draft, setDraft] = useState("");
  const idRef = useRef(0);
  const transcriptRef = useRef<HTMLDivElement>(null);
  // Only auto-scroll while the reader is already at/near the bottom —
  // never hijack a scroll-up
  const nearBottomRef = useRef(true);

  useEffect(() => {
    if (!demoMode) return;
    api
      .getDemoQuestions()
      .then(setDemoQuestions)
      .catch(() => setDemoQuestions([]));
  }, [demoMode]);

  const suggestions = demoMode ? demoQuestions : STARTER_QUESTIONS;
  const asked = new Set(exchanges.map((x) => x.question));
  const loading = exchanges.some((x) => x.status === "loading");

  const handleScroll = () => {
    const el = transcriptRef.current;
    if (!el) return;
    nearBottomRef.current =
      el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  // Follow the newest message on send and on answer arrival
  const transcriptKey = exchanges.map((x) => `${x.id}:${x.status}`).join(",");
  useEffect(() => {
    const el = transcriptRef.current;
    if (el && nearBottomRef.current) {
      requestAnimationFrame(() =>
        el.scrollTo?.({ top: el.scrollHeight, behavior: "smooth" })
      );
    }
  }, [transcriptKey]);

  const runAsk = async (id: number, question: string) => {
    try {
      const answer = await api.ask(question);
      setExchanges((xs) =>
        xs.map((x) => (x.id === id ? { ...x, status: "done", answer } : x))
      );
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Something went wrong.";
      setExchanges((xs) =>
        xs.map((x) =>
          x.id === id ? { ...x, status: "error", error: message } : x
        )
      );
    }
  };

  const send = (q: string) => {
    const question = q.trim();
    if (!question || loading) return;
    const id = ++idRef.current;
    // A new exchange means the user wants to see it — resume following
    nearBottomRef.current = true;
    setExchanges((xs) => [...xs, { id, question, status: "loading" }]);
    void runAsk(id, question);
  };

  const retry = (id: number) => {
    const target = exchanges.find((x) => x.id === id);
    if (!target) return;
    setExchanges((xs) =>
      xs.map((x) =>
        x.id === id ? { ...x, status: "loading", error: undefined } : x
      )
    );
    void runAsk(id, target.question);
  };

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      {/* Transcript — the only scrolling region on this screen */}
      <div
        ref={transcriptRef}
        onScroll={handleScroll}
        className="flex-1 min-h-0 overflow-y-auto no-scrollbar space-y-2.5 px-1 pt-2 pb-3"
      >
        {exchanges.length === 0 && (
          <CoachBubble>
            <p className="text-sm leading-relaxed text-ink">
              {demoMode
                ? "Ask me about this runner's history — try one of the questions below."
                : "Ask me anything about your runs — or start with a suggestion."}
            </p>
          </CoachBubble>
        )}
        {exchanges.map((x) => (
          <div key={x.id} className="space-y-2.5">
            <div className="ml-auto w-fit max-w-[80%] bg-[#0A6B59] text-white text-sm leading-relaxed px-3.5 py-2.5 rounded-[14px] rounded-br-[3px]">
              {x.question}
            </div>
            {x.status === "loading" && <TypingBubble />}
            {x.status === "error" && (
              <CoachBubble>
                <p className="text-sm leading-relaxed text-ink">
                  {x.error ?? "Couldn't answer that."}
                </p>
                <button
                  type="button"
                  onClick={() => retry(x.id)}
                  className="tap-target mt-1.5 text-[12.5px] font-semibold text-[#0FA98E]"
                >
                  Retry
                </button>
              </CoachBubble>
            )}
            {x.status === "done" && x.answer && (
              <CoachBubble>
                <AiText text={x.answer.answer} />
                {x.answer.cited_runs.length > 0 && (
                  <div className="mt-3">
                    <p className="text-[11px] text-clay mb-1">
                      Based on these runs:
                    </p>
                    <ul className="space-y-1">
                      {x.answer.cited_runs.map((run) => (
                        <li key={run.run_id}>
                          <Link
                            href={`/runs/${run.run_id}`}
                            className="block text-sm text-leaf-deep hover:underline"
                          >
                            {formatDate(run.date)}
                            {run.city ? ` · ${run.city}` : ""}
                            <span className="block text-[12px] text-clay">
                              {RUN_TYPE_LABELS[run.run_type]} ·{" "}
                              {formatDistance(run.distance_km)}
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CoachBubble>
            )}
          </div>
        ))}
      </div>

      {/* Composer — in flow above the bottom nav; never position:fixed */}
      <div className="shrink-0 border-t-[0.5px] border-line bg-cream pt-2 pb-2 space-y-2">
        {suggestions.length > 0 && (
          <div className="relative">
            <div className="flex gap-2 overflow-x-auto no-scrollbar px-1 pr-8">
              {suggestions.map((q) => {
                const wasAsked = asked.has(q);
                return (
                  <button
                    key={q}
                    type="button"
                    disabled={loading}
                    onClick={() => send(q)}
                    className={`tap-target shrink-0 whitespace-nowrap text-[13px] px-3.5 py-1.5 rounded-[99px] border text-[#0A6B59] disabled:opacity-50 ${
                      wasAsked
                        ? "bg-leaf-pale border-leaf-soft"
                        : "bg-white border-[#F0E8DD] hover:bg-white/80"
                    }`}
                  >
                    {wasAsked ? "✓ " : ""}
                    {q}
                  </button>
                );
              })}
            </div>
            {/* Right-edge fade: the rail reads as scrollable */}
            <div
              aria-hidden
              className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-r from-transparent to-cream"
            />
          </div>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (demoMode) return; // chips are the interaction in demo
            send(draft);
            setDraft("");
          }}
          className="flex gap-2 px-1"
        >
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={demoMode}
            placeholder={
              demoMode
                ? "Free-form ask works in the full app"
                : "Ask a question about your runs…"
            }
            className="flex-1 min-w-0 bg-white border-[0.5px] border-line rounded-full px-3.5 py-2 text-sm text-ink placeholder:text-sand focus:outline-none focus:ring-1 focus:ring-leaf disabled:text-sand disabled:bg-white/60"
          />
          {!demoMode && (
            <button
              type="submit"
              disabled={loading || !draft.trim()}
              className="tap-target px-4 py-2 text-sm rounded-full bg-leaf-deep text-white disabled:bg-leaf-soft disabled:text-leaf-deep/70"
            >
              Send
            </button>
          )}
        </form>
      </div>
    </div>
  );
}

function CoachBubble({ children }: { children: React.ReactNode }) {
  return (
    <div className="mr-auto w-fit max-w-[88%] glass-ai rounded-[14px] rounded-bl-[3px] p-3.5">
      {children}
    </div>
  );
}

function TypingBubble() {
  return (
    <CoachBubble>
      <span className="flex gap-1 py-0.5" aria-label="Coach is thinking">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="typing-dot w-1.5 h-1.5 rounded-full bg-[#0A6B59]"
            style={{ animationDelay: `${i * 0.18}s` }}
          />
        ))}
      </span>
    </CoachBubble>
  );
}
