from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import DataSource, ImportJobStatus, ImportJobType


class ImportJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: DataSource
    job_type: ImportJobType
    status: ImportJobStatus
    items_total: int | None
    items_imported: int
    items_skipped_duplicates: int
    items_failed: int
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    created_at: datetime
