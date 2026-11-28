"""Admin del escenario: ``POST /api/v1/admin/reset``.

Operación destructiva sobre los datos derivados (inventario, eventos, alertas,
observaciones, baselines y discovery). Requiere el mismo Bearer de ingesta y
nunca toca los pods de la red. Si hay un ciclo de discovery en curso devuelve
409 vía ``ConflictError``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from ..reset.service import ResetService
from .deps import get_reset, require_ingest_token
from .schemas import ResetResult

router = APIRouter(tags=["admin"])


@router.post(
    "/admin/reset",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_ingest_token)],
    response_model=ResetResult,
)
def reset_scenario(
    request: Request,
    reset: ResetService = Depends(get_reset),
) -> ResetResult:
    result = reset.reset()
    condition = getattr(request.app.state, "condition", None)
    if condition is not None:
        condition.reset()
    return result
