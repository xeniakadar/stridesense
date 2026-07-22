"""Daily overview: a grounded 2-3 sentence morning brief.

Same design as insights.py — the LLM narrates ONLY the structured context
assembled here (sleep vs own average, readiness, current ACWR, days since
the last hard run). Sections for missing data are simply absent; the
prompt describes and offers options, never prescribes.
"""

from dataclasses import dataclass
from datetime import date as date_type
from datetime import timedelta
from uuid import UUID

from anthropic import AsyncAnthropic
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import DailyBrief, Run, SleepRecord
from app.models.enums import RunType
from app.services.insights import InsightUnavailableError
from app.services.training_load import (
    ACUTE_WINDOW_DAYS,
    CHRONIC_WINDOW_DAYS,
    _session_load,
    _zone,
)

DAILY_BRIEF_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 300

# "Hard" here means intensity, not volume — the sessions that ask the most
# of recovery. Long runs are load, but not a hard-day signal by themselves.
HARD_RUN_TYPES = {RunType.INTERVAL, RunType.TEMPO, RunType.RACE}


@dataclass
class DailyBriefData:
    sleep_score: int | None
    sleep_score_avg: float | None
    readiness_score: int | None
    acwr: float | None
    zone: str | None
    days_since_hard_run: int | None

    def has_anything(self) -> bool:
        return any(
            v is not None
            for v in (self.sleep_score, self.readiness_score, self.acwr,
                      self.days_since_hard_run)
        )


async def invalidate_daily_briefs(
    session: AsyncSession, user_id: UUID, dates: list[date_type]
) -> None:
    """Delete cached briefs for the given days so the next GET regenerates.

    Call from any code path that writes new recovery data for a date —
    today that's the Oura sync upsert. Doesn't commit; batches into the
    caller's own commit.
    """
    if not dates:
        return
    await session.execute(
        delete(DailyBrief).where(
            DailyBrief.user_id == user_id, DailyBrief.date.in_(dates)
        )
    )


def _current_load_point(
    runs: list[Run], today: date_type
) -> tuple[float | None, str | None]:
    """Today's ACWR + zone. compute_load_series stops at the last run date,
    so compute the point for `today` directly with the same math."""
    if not runs:
        return None, None
    load_by_day: dict[date_type, float] = {}
    for r in runs:
        load_by_day[r.date] = load_by_day.get(r.date, 0.0) + _session_load(r)
    acute = sum(
        load_by_day.get(today - timedelta(days=i), 0.0)
        for i in range(ACUTE_WINDOW_DAYS)
    ) / ACUTE_WINDOW_DAYS
    chronic = sum(
        load_by_day.get(today - timedelta(days=i), 0.0)
        for i in range(CHRONIC_WINDOW_DAYS)
    ) / CHRONIC_WINDOW_DAYS
    if chronic <= 0:
        return None, None
    acwr = round(acute / chronic, 2)
    return acwr, _zone(acwr)


async def gather_daily_data(
    session: AsyncSession, user_id: UUID, today: date_type
) -> DailyBriefData:
    """Collect the brief's inputs from existing tables. Missing data stays None."""
    # Last night's sleep: the record dated today (night into this morning),
    # falling back to yesterday's if this morning's sync hasn't landed yet.
    result = await session.execute(
        select(SleepRecord)
        .where(
            SleepRecord.user_id == user_id,
            SleepRecord.date >= today - timedelta(days=1),
            SleepRecord.date <= today,
        )
        .order_by(SleepRecord.date.desc())
    )
    last_night = result.scalars().first()

    sleep_score = last_night.sleep_quality if last_night else None
    readiness_score = None
    if last_night and last_night.raw_payload:
        readiness_score = last_night.raw_payload.get("daily_readiness", {}).get(
            "score"
        )

    avg_result = await session.execute(
        select(func.avg(SleepRecord.sleep_quality)).where(
            SleepRecord.user_id == user_id, SleepRecord.sleep_quality.isnot(None)
        )
    )
    avg = avg_result.scalar_one_or_none()
    sleep_score_avg = round(float(avg), 1) if avg is not None else None

    runs_result = await session.execute(select(Run).where(Run.user_id == user_id))
    runs = list(runs_result.scalars().all())

    acwr, zone = _current_load_point(runs, today)

    hard_dates = [
        r.date for r in runs if r.run_type in HARD_RUN_TYPES and r.date <= today
    ]
    days_since_hard_run = (today - max(hard_dates)).days if hard_dates else None

    return DailyBriefData(
        sleep_score=sleep_score,
        sleep_score_avg=sleep_score_avg,
        readiness_score=readiness_score,
        acwr=acwr,
        zone=zone,
        days_since_hard_run=days_since_hard_run,
    )


def build_daily_context(data: DailyBriefData, today: date_type) -> str:
    """Assemble the factual context block. No section for missing data."""
    lines: list[str] = [f"Today is {today.isoformat()}."]

    if data.sleep_score is not None:
        lines.append("\n## Last night's sleep (Oura score, 0-100)")
        lines.append(f"- Score: {data.sleep_score}")
        if data.sleep_score_avg is not None:
            lines.append(f"- This runner's own average: {data.sleep_score_avg}")

    if data.readiness_score is not None:
        lines.append("\n## Readiness (Oura score, 0-100)")
        lines.append(f"- Score: {data.readiness_score}")

    if data.acwr is not None:
        lines.append("\n## Training load")
        lines.append(f"- ACWR today: {data.acwr} (zone: {data.zone})")
        lines.append("- ACWR 0.8-1.3 is the optimal range; above 1.5 is high-risk.")

    if data.days_since_hard_run is not None:
        lines.append("\n## Last hard run (interval/tempo/race)")
        lines.append(f"- {data.days_since_hard_run} day(s) ago")

    return "\n".join(lines)


DAILY_BRIEF_SYSTEM_PROMPT = """You are a running-analytics assistant writing \
a short morning overview of how a runner comes into the day. Rules:
- Describe only what the provided data shows. Never invent numbers or facts.
- Offer options, never prescriptions — the reader decides what to do. No \
"you should", no workout assignments.
- Never reference training plans or schedules; none exist.
- You are not a doctor: no medical advice, no diagnoses.
- Permissive, low-pressure tone (e.g. "an easy day would cost you nothing").
- 2-3 sentences. Plain language, no jargon dumps.
"""


async def generate_daily_brief(data: DailyBriefData, today: date_type) -> str:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise InsightUnavailableError("ANTHROPIC_API_KEY is not configured")

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    context = build_daily_context(data, today)
    try:
        message = await client.messages.create(
            model=DAILY_BRIEF_MODEL,
            max_tokens=MAX_TOKENS,
            system=DAILY_BRIEF_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Here is today's data:\n\n{context}\n\n"
                        "Write the morning overview."
                    ),
                }
            ],
        )
    except Exception as e:
        raise InsightUnavailableError(f"Daily brief generation failed: {e}") from e

    return "".join(
        block.text for block in message.content if block.type == "text"
    ).strip()
