from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_session
from app.core.config import get_settings
from app.schemas.analytics import AskAnswerRead, AskRequest, CitedRunRead
from app.services.ask import ASK_MODEL, generate_answer, retrieve
from app.services.insights import InsightUnavailableError

router = APIRouter(prefix="/ask", tags=["ask"])


@router.post("", response_model=AskAnswerRead)
async def ask_endpoint(
    payload: AskRequest,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> AskAnswerRead:
    if get_settings().demo_mode:
        raise HTTPException(
            status_code=403,
            detail=(
                "Ask is switched off in the public demo — free-form questions "
                "would let anyone generate text through our LLM. Clone the "
                "repo and run it locally to try it on your own data!"
            ),
        )

    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty")

    retrieved = await retrieve(session, user_id, question, k=5)
    if not retrieved:
        return AskAnswerRead(
            answer=(
                "No searchable runs yet — import some runs, then embed them "
                "with scripts/embed_runs.py."
            ),
            model=None,
            cited_runs=[],
        )

    try:
        answer = await generate_answer(question, retrieved)
    except InsightUnavailableError as e:
        raise HTTPException(
            status_code=503, detail="Ask temporarily unavailable"
        ) from e

    return AskAnswerRead(
        answer=answer,
        model=ASK_MODEL,
        cited_runs=[
            CitedRunRead(
                run_id=run.id,
                date=run.date,
                run_type=run.run_type,
                distance_km=run.distance_km,
                score=round(score, 3),
            )
            for run, score in retrieved
        ],
    )
