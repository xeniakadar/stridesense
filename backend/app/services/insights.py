"""Generate grounded, plain-language insights about a run using an LLM.

The model reasons ONLY over the structured context we assemble. No external
knowledge about the specific run, no invented numbers."""

from uuid import UUID

from anthropic import AsyncAnthropic
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Insight, Run
from app.services.similarity import SimilarRun
from app.services.training_load import LoadPoint

INSIGHT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 600


class InsightUnavailableError(Exception):
    """Raised when insight generation can't proceed (no key, API failure)."""


async def invalidate_insights(session: AsyncSession, run_id: UUID) -> None:
    """Delete cached insights for a run so the next GET regenerates fresh.

    Call this from every code path that changes a run's insight-relevant
    fields — weather enrichment, glucose summary computation, the run
    update endpoint (run_type/distance/duration/HR), classify_runs.py
    --apply — so an insight never keeps narrating data the run no longer
    has. Doesn't commit; batches into the caller's own commit.
    """
    await session.execute(delete(Insight).where(Insight.run_id == run_id))


def _format_pace(seconds_per_km: float | None) -> str:
    if not seconds_per_km or seconds_per_km <= 0:
        return "unknown"
    m, s = divmod(round(seconds_per_km), 60)
    return f"{m}:{s:02d}/km"


def build_context(
    run: Run,
    similar: list[SimilarRun],
    load: LoadPoint | None,
) -> str:
    """Assemble the factual context block. Every line is real data."""
    lines: list[str] = []
    lines.append("## This run")
    lines.append(f"- Date: {run.date}")
    lines.append(f"- Type: {run.run_type.value}")
    lines.append(f"- Distance: {run.distance_km} km")
    lines.append(f"- Pace: {_format_pace(run.avg_pace_seconds_per_km)}")
    if run.avg_hr:
        lines.append(f"- Average heart rate: {run.avg_hr} bpm")
    if run.perceived_effort:
        lines.append(f"- Perceived effort (RPE): {run.perceived_effort}/10")

    if run.weather_temp_start_c is not None:
        lines.append("\n## Weather during the run")
        lines.append(
            f"- Temp start/end: {run.weather_temp_start_c}/{run.weather_temp_end_c} C"
        )
        if run.weather_humidity_avg is not None:
            lines.append(f"- Avg humidity: {run.weather_humidity_avg}%")
        if run.weather_apparent_temp_max_c is not None:
            lines.append(f"- Apparent max temp: {run.weather_apparent_temp_max_c} C")

    if run.glucose_at_start_mg_dl is not None:
        lines.append("\n## Glucose (mg/dL)")
        lines.append(f"- Pre-run 60min avg: {run.glucose_pre_run_60min_avg_mg_dl}")
        lines.append(f"- At start: {run.glucose_at_start_mg_dl}")
        lines.append(f"- At end: {run.glucose_at_end_mg_dl}")
        lines.append(
            f"- Min/Max during: {run.glucose_min_during_run_mg_dl}"
            f"/{run.glucose_max_during_run_mg_dl}"
        )
        lines.append(
            f"- Time in range during run: {run.glucose_time_in_range_pct_during_run}%"
        )

    if load and load.acwr is not None:
        lines.append("\n## Training load")
        lines.append(f"- ACWR on this day: {load.acwr} (zone: {load.zone})")
        lines.append("- ACWR 0.8-1.3 is the optimal range; above 1.5 is high-risk.")

    if similar:
        lines.append("\n## Comparable past runs")
        for s in similar[:3]:
            lines.append(
                f"- {s.run.date} {s.run.run_type.value} {s.run.distance_km}km "
                f"@ {_format_pace(s.run.avg_pace_seconds_per_km)} "
                f"(similarity {s.score:.2f})"
            )

    return "\n".join(lines)


SYSTEM_PROMPT = """You are a running-analytics assistant. You explain why a \
run likely felt the way it did, using ONLY the structured data provided. \
Rules:
- Reason strictly from the data given. Never invent numbers, paces, or facts.
- If the data doesn't support a claim, don't make it.
- Compare the run to the provided comparable runs when relevant.
- Mention training load (ACWR) only if it's provided.
- Plain language, no jargon dumps.
- Structure the output exactly like this, and never as one long block:
  1. First line: a one-sentence verdict, entirely bolded with **...** — \
the single takeaway, e.g. "**This run felt easy because it was easy — \
familiar pace, no fatigue, only the humidity pushed back.**"
  2. Then at most 2-3 short paragraphs, one theme each, in this order \
when the data exists: training load / pace; weather / heart rate; \
glucose. Each under ~40 words, with exactly ONE key clause bolded. \
Skip a theme rather than pad it.
  3. Then, if specific comparable runs or numbers support the claim, \
finish with 1-3 short evidence lines starting with "- ".
- No headers, no other markdown beyond the bolding and evidence dashes.
- Write dates in long form (e.g. "May 14, 2026"), never ISO like 2026-05-14.
- You are not a doctor; do not give medical advice. For glucose, describe \
patterns factually (e.g. "glucose trended down across the run") without \
diagnosing.
"""


async def generate_insight(
    run: Run,
    similar: list[SimilarRun],
    load: LoadPoint | None,
) -> str:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise InsightUnavailableError("ANTHROPIC_API_KEY is not configured")

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    context = build_context(run, similar, load)
    try:
        message = await client.messages.create(
            model=INSIGHT_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Here is the data for a run:\n\n{context}\n\n"
                        "Explain why this run likely felt the way it did."
                    ),
                }
            ],
        )
    except Exception as e:
        raise InsightUnavailableError(f"Insight generation failed: {e}") from e

    return "".join(
        block.text for block in message.content if block.type == "text"
    ).strip()
