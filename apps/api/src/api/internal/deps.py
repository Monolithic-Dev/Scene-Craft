from typing import Annotated

from fastapi import Depends, Header

from src.core.config import get_settings
from src.core.exceptions import UnauthorizedError

settings = get_settings()


def require_internal_service(
    x_internal_service_key: Annotated[str | None, Header()] = None,
) -> None:
    """Guards every /internal/* route — mcp_server is the only caller.

    Shared-secret header check, not JWT: these routes have no end-user
    session, only a trusted service-to-service caller. See config.py's
    internal_service_key docstring for the Phase 6 IAM/mTLS replacement path.
    """
    if x_internal_service_key is None or x_internal_service_key != settings.internal_service_key:
        raise UnauthorizedError("Missing or invalid internal service key")


RequireInternalService = Annotated[None, Depends(require_internal_service)]
