"use client";

import Link from "next/link";
import { useState } from "react";

import { api, ApiError } from "@/lib/api";
import { formatDate, RUN_TYPE_LABELS } from "@/lib/format";
import type { AskAnswer } from "@/lib/types";

export function AskSection() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AskAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = question.trim();
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

  return (
    <div className="bg-white border border-gray-200 rounded p-5">
      <div className="mb-4">
        <h2 className="text-base font-medium">Ask your history</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          e.g. &ldquo;how do I handle hot weather?&rdquo; — answers cite your own runs
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about your runs…"
          className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-gray-400"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="px-4 py-2 text-sm rounded bg-gray-900 text-white disabled:opacity-40"
        >
          {loading ? "Thinking…" : "Ask"}
        </button>
      </form>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      {result && (
        <div className="mt-4 space-y-3">
          <p className="text-sm whitespace-pre-wrap">{result.answer}</p>
          {result.cited_runs.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 mb-1">Based on these runs:</p>
              <ul className="space-y-1">
                {result.cited_runs.map((run) => (
                  <li key={run.run_id}>
                    <Link
                      href={`/runs/${run.run_id}`}
                      className="text-sm text-blue-600 hover:underline"
                    >
                      {formatDate(run.date)} — {RUN_TYPE_LABELS[run.run_type]},{" "}
                      {run.distance_km} km
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
