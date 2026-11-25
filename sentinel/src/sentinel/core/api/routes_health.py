"""``GET /api/v1/health`` — estado derivado de la BD (ST-M4-08, Q11)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..health.service import HealthService
from .deps import get_health
from .schemas import HealthStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def health(service: HealthService = Depends(get_health)) -> HealthStatus:
    return service.health()
