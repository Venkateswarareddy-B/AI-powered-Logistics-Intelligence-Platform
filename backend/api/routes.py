"""Route comparison API endpoint."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.services.route_service import compare_routes

router = APIRouter(prefix="/api/routes", tags=["routes"])


class RouteCompareRequest(BaseModel):
    shipment_id: str
    alternative_route_id: str | None = None


@router.post("/compare")
def route_compare(
    req: RouteCompareRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Compare current route with alternatives for a shipment."""
    result = compare_routes(db, req.shipment_id, req.alternative_route_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result
