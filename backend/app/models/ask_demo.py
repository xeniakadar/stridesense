import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AskDemoAnswer(Base):
    """A curated ask-your-history Q&A pair, served verbatim in demo mode.

    Written once at deploy time by scripts/pregenerate_ask_answers.py;
    POST /ask in demo mode only ever reads these rows. cited_runs holds
    the CitedRunRead-shaped dicts captured at generation time.
    """

    __tablename__ = "ask_demo_answers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    question: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    cited_runs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
