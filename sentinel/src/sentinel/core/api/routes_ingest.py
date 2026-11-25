"""``POST /api/v1/ingest`` — ST-M4-01/03 (FD §3.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from sentinel.foundation.models import Batch

from ..ingestion.service import IngestionService, IngestResult
from .deps import get_ingestion, require_ingest_token

router = APIRouter(tags=["ingest"])


@router.post(
    "/ingest",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_ingest_token)],
    response_model=IngestResult,
)
def ingest(
    batch: Batch,
    ingestion: IngestionService = Depends(get_ingestion),
) -> IngestResult:
    return ingestion.process(batch)
