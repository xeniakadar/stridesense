"use client";

import ReactMarkdown from "react-markdown";

/** Renderer for AI-generated text (insights, ask answers, daily brief).
 *
 * The prompts ask for plain prose, but older cached content may contain
 * markdown — render it properly instead of showing raw asterisks. The
 * `.ai-text` rules in globals.css keep every element on the glass-card
 * typography scale. */
export function AiText({
  text,
  className = "",
}: {
  text: string;
  className?: string;
}) {
  return (
    <div className={`ai-text text-sm leading-relaxed text-ink ${className}`}>
      <ReactMarkdown>{text}</ReactMarkdown>
    </div>
  );
}
