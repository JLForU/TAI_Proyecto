"""Trigger de discovery: ``POST /discovery``, ``GET /discovery/{run_id}`` (P2).

U4 (FD §3.2, BR-U4-08/31): si el proceso tiene config de scope, cada host
valida contra la allowlist **antes** de crear el run ⇒ ``ScopeError`` → 400
``scope_violation`` (handler U2) + warning log; sin config (D-U4-04) la
garantía la da el worker en la Ruta A.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from sentinel.foundation.errors import ScopeError, ValidationError
from sentinel.foundation.logging import get_logger

from ..discovery.trigger import DiscoveryTrigger
from ..errors import NotFoundError
from .deps import get_discovery
from .schemas import DiscoveryRequest, DiscoveryRunStatus

router = APIRouter(tags=["discovery"])

_log = get_logger("discovery.api")

_MAX_HOSTS = 1000


@router.post(
    "/discovery",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DiscoveryRunStatus,
)
def trigger_discovery(
    request: DiscoveryRequest,
    trigger: DiscoveryTrigger = Depends(get_discovery),
) -> DiscoveryRunStatus:
    hosts = [h.strip() for h in request.hosts if h.strip()]
    if not hosts:
        raise ValidationError("hosts must not be empty")
    if len(hosts) > _MAX_HOSTS:
        raise ValidationError(f"too many hosts (max {_MAX_HOSTS})")
    validator = trigger.scope_validator
    if validator is not None:
        result = validator.validate_scope(hosts)
        if not result.ok:
            detail = result.errors[0] if result.errors else "host fuera de alcance"
            _log.warning(
                "host rejected before run creation",
                extra={"event": "scope_violation", "detail": detail, "hosts": len(hosts)},
            )
            raise ScopeError(detail)
    return trigger.trigger(hosts, request.timeout_seconds)


@router.get("/discovery/{run_id}", response_model=DiscoveryRunStatus)
def discovery_status(
    run_id: str,
    trigger: DiscoveryTrigger = Depends(get_discovery),
) -> DiscoveryRunStatus:
    result = trigger.get_status(run_id)
    if result is None:
        raise NotFoundError(f"discovery run {run_id} not found")
    return result
