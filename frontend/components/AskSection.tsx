"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AiText } from "@/components/AiText";
import { useDemoMode } from "@/components/DemoProvider";
import { TertiaryLink } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatDistance, RUN_TYPE_LABELS } from "@/lib/format";
import type { AskAnswer } from "@/lib/types";

const STARTER_QUESTIONS = [
  "How do I handle hot weather?",
  "Tell me about my races",
  "How has my pace changed?",
];

export function AskSection() {
  const demoMode = useDemoMode();
  const [question, setQuestion] = useState("");
  const [demoQuestions, setDemoQuestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AskAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);

  const suggestions = demoMode ? demoQuestions : STARTER_QUESTIONS;

  useEffect(() => {
    if (!demoMode) return;
    api
      .getDemoQuestions()
      .then(setDemoQuestions)
      .catch(() => setDemoQuestions([]));
  }, [demoMode]);

  async function submit(q: string) {
    const trimmed = q.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.ask(trimmed));
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Something went wrong — try again."
      );
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    submit(question);
  }

  return (
    <div className="glass-ai rounded-2xl p-4">
      <div className="mb-4">
        <h2 className="text-[20px] font-medium text-leaf-deep leading-snug">Ask your history</h2>
        <p className="text-[13px] text-clay mt-0.5">
          {demoMode
            ? "In this demo, try one of these — free-form ask works in the full app"
            : "e.g. “how do I handle hot weather?” — answers cite your own runs"}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={demoMode}
          placeholder={
            demoMode
              ? "Pick an example question below"
              : "Ask a question about your runs…"
          }
          className="flex-1 min-w-0 bg-white/70 border-[0.5px] border-white/80 rounded-full px-3.5 py-2 text-sm text-ink placeholder:text-sand focus:outline-none focus:ring-1 focus:ring-leaf disabled:text-sand"
        />
        {/* In demo mode the button would be permanently disabled — the
            chips are the interaction, so don't render a dead CTA */}
        {!demoMode && (
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="px-4 py-2 text-sm rounded-full bg-leaf-deep text-white disabled:bg-leaf-soft disabled:text-leaf-deep/70"
          >
            {loading ? "Thinking…" : "Ask"}
          </button>
        )}
      </form>

      {!result && suggestions.length > 0 && (
        <div className="mt-3 -mx-4 px-4 flex gap-2 overflow-x-auto no-scrollbar">
          {suggestions.map((q) => (
            <button
              key={q}
              type="button"
              disabled={loading}
              onClick={() => {
                setQuestion(q);
                submit(q);
              }}
              className="tap-target shrink-0 whitespace-nowrap text-[13px] px-3.5 py-1.5 rounded-[99px] bg-white border border-[#F0E8DD] text-[#0A6B59] hover:bg-white/80 disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {error && <p className="mt-4 text-sm text-red-700">{error}</p>}

      {result && (
        <div className="mt-4 space-y-3">
          <AiText text={result.answer} />
          {result.cited_runs.length > 0 && (
            <div>
              <p className="text-[11px] text-clay mb-1">Based on these runs:</p>
              <ul className="space-y-1">
                {result.cited_runs.map((run) => (
                  <li key={run.run_id}>
                    {/* date · city / type · distance — the city keeps hot
                        runs in cold months from reading as contradictions */}
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
          <TertiaryLink
            onClick={() => {
              setResult(null);
              setQuestion("");
            }}
          >
            Ask another question
          </TertiaryLink>
        </div>
      )}
    </div>
  );
}
