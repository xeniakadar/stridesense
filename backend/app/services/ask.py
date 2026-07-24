"""Ask-your-history RAG: turn runs into text, embed them, retrieve, answer.

Retrieval-side vectors live in runs.embedding (pgvector, 384 dims), computed
ahead of time by scripts/embed_runs.py from run_to_text(run). At request time
only the question is embedded; ranking happens in Postgres via the cosine
operator. The answer is generated over a grounded context block built from
the retrieved runs — same pattern as insights.py: the model narrates the
data, it cannot deviate from it.
"""

import hashlib
from typing import TYPE_CHECKING
from uuid import UUID

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Run
from app.services.insights import InsightUnavailableError

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

ASK_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 600

_model: "SentenceTransformer | None" = None

def get_model() -> "SentenceTransformer":
    """Load the embedding model once, reuse it forever.

    Imported lazily: this module loads at app startup (via the /ask router),
    and a top-level sentence_transformers import would pull torch into every
    uvicorn boot and test run.
    """
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def embed(texts: list[str]):
    """Turn sentences into vectors. Returns a numpy array, one row per text."""
    return get_model().encode(texts, normalize_embeddings=True)

def sentence_hash(text: str) -> str:
    """Fingerprint of a run's sentence — changes iff run_to_text output does.

    Stored next to the embedding so embed_runs.py can tell which runs are
    stale (re-imported, re-classified, weather-enriched, ...) without
    re-embedding everything.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def run_to_text(run: Run) -> str:
    """Render one run as one retrieval-friendly sentence."""
    parts = []
    if run.run_type.value != "other":
      parts.append(f"{run.run_type.value} run, {run.distance_km} km")
    else:
      parts.append(f"run of {run.distance_km} km")
    if run.weather_temp_start_c is not None:
        temp = run.weather_temp_start_c
        if temp >= 24:
            parts.append(f"in hot {temp:.0f}°C weather")
        elif temp <= 5:
            parts.append(f"in cold {temp:.0f}°C weather")
        else:
            parts.append(f"in {temp:.0f}°C weather")
    if run.start_lat is not None:
        lat = run.start_lat
        if 47 <= lat < 48:
            parts.append("in Budapest")
        elif 40 <= lat < 41:
            parts.append("in NYC")
        elif 38 <= lat < 39:
            parts.append("in Lisbon")
        elif 41 <= lat < 42:
            parts.append("in Chicago")

    if run.avg_pace_seconds_per_km is not None:
        pace = run.avg_pace_seconds_per_km
        if pace < 360:
            parts.append(f"at a fast pace of {pace//60:.0f}:{pace%60:02.0f} min/km")
        elif pace > 480:
            parts.append(f"at a slow pace of {pace//60:.0f}:{pace%60:02.0f} min/km")
        else:
            parts.append(f"at a moderate pace of {pace//60:.0f}:{pace%60:02.0f} min/km")
    return " ".join(parts)

async def retrieve(
    session: AsyncSession, user_id: UUID, question: str, k: int = 5
) -> list[tuple[Run, float]]:
    """Find the k runs most relevant to the question. Returns (run, score) pairs.

    Only the question is embedded here; run vectors are read from
    runs.embedding. pgvector's <=> (cosine_distance) does the ranking in
    Postgres, and score = 1 - distance = cosine similarity, matching the
    dot-product scores of the old in-memory version (vectors are normalized).
    Runs never embedded by embed_runs.py are invisible to retrieval.
    """
    query_vec = embed([question])[0]
    distance = Run.embedding.cosine_distance(query_vec)
    result = await session.execute(
        select(Run, distance)
        .where(Run.user_id == user_id, Run.embedding.isnot(None))
        .order_by(distance)
        .limit(k)
    )
    return [(run, 1.0 - dist) for run, dist in result.all()]


def build_ask_context(retrieved: list[tuple[Run, float]]) -> str:
    """Assemble the factual context block. Every line is real data."""
    lines = ["## Relevant runs from the user's history (most relevant first)"]
    for run, score in retrieved:
        lines.append(f"- {run.date}: {run_to_text(run)} (relevance {score:.2f})")
    return "\n".join(lines)


ASK_SYSTEM_PROMPT = """You are a running-analytics assistant answering a \
question about the user's own run history. Rules:
- Answer ONLY from the runs listed in the context. Never invent runs, \
numbers, paces, or facts.
- Cite the date of every run you draw on, in long form, e.g. "your run \
on May 14, 2026" — never ISO dates like 2026-05-14.
- If the listed runs don't actually answer the question, say so plainly \
instead of stretching.
- Plain language, no jargon dumps.
- Structure the output exactly like this, and never as one long block:
  1. First line: a one-sentence verdict, entirely bolded with **...** — \
the direct answer to the question.
  2. Then at most 2 short paragraphs (1-2 sentences each), each with \
exactly ONE key clause bolded.
  3. Then, if specific runs support the answer, finish with 1-3 short \
evidence lines starting with "- ", each citing its run's date.
- No headers, no other markdown beyond the bolding and evidence dashes.
- You are not a doctor; do not give medical advice.
"""


async def generate_answer(question: str, retrieved: list[tuple[Run, float]]) -> str:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise InsightUnavailableError("ANTHROPIC_API_KEY is not configured")

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    context = build_ask_context(retrieved)
    try:
        message = await client.messages.create(
            model=ASK_MODEL,
            max_tokens=MAX_TOKENS,
            system=ASK_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"{context}\n\n"
                        f"The user asks: {question}\n\n"
                        "Answer using only the runs above, citing their dates."
                    ),
                }
            ],
        )
    except Exception as e:
        raise InsightUnavailableError(f"Answer generation failed: {e}") from e

    return "".join(
        block.text for block in message.content if block.type == "text"
    ).strip()
