"""Activity monitoring endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_snapshot, verify_api_key
from src.api.schemas import (
    ActivityResponse,
    ActivitySummaryItem,
    ParticipantItem,
)

router = APIRouter(prefix="/api", tags=["activity"])


def _find_participants_by_ficha(snapshot: dict, ficha: str) -> dict:
    """Find course participants by ficha number. Raises 404 if not found."""
    for cp in snapshot.get("participants", []):
        if cp["ficha"] == ficha:
            return cp
    raise HTTPException(status_code=404, detail=f"Participants for ficha {ficha} not found")


@router.get("/activity", response_model=list[ActivitySummaryItem])
def activity_summary(
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Summary of activity across all fichas."""
    result: list[ActivitySummaryItem] = []

    for cp in snapshot.get("participants", []):
        participants = cp.get("participants", [])
        if not participants:
            continue

        active = sum(1 for p in participants if p["status"] == "Activo")
        suspended = sum(1 for p in participants if p["status"] == "Suspendido")

        # Calculate avg days since access (exclude "Nunca" = 9999 and unknown = -1)
        valid_days = [
            p["last_access_days"] for p in participants
            if 0 <= p["last_access_days"] < 9999
        ]
        avg_days = round(sum(valid_days) / len(valid_days), 1) if valid_days else 0.0

        inactive_30 = sum(
            1 for p in participants
            if p["last_access_days"] >= 30 and p["last_access_days"] != 9999
        )
        # Also count "Nunca" as inactive 30+
        inactive_30 += sum(1 for p in participants if p["last_access_days"] == 9999)

        result.append(ActivitySummaryItem(
            ficha=cp["ficha"],
            course_id=cp["course_id"],
            total_participants=len(participants),
            total_active=active,
            total_suspended=suspended,
            avg_days_since_access=avg_days,
            inactive_30_plus=inactive_30,
        ))

    return result


@router.get("/activity/{ficha}", response_model=ActivityResponse)
def activity_detail(
    ficha: str,
    min_days_inactive: int | None = None,
    snapshot: dict = Depends(get_snapshot),
    _key: str = Depends(verify_api_key),
):
    """Participants for a specific ficha, with optional inactivity filter."""
    cp = _find_participants_by_ficha(snapshot, ficha)
    participants = cp.get("participants", [])

    # Apply filter
    if min_days_inactive is not None:
        participants = [
            p for p in participants
            if p["last_access_days"] >= min_days_inactive
        ]

    active = sum(1 for p in participants if p["status"] == "Activo")
    suspended = sum(1 for p in participants if p["status"] == "Suspendido")

    items = [
        ParticipantItem(
            user_id=p["user_id"],
            full_name=p["full_name"],
            document=p["document"],
            email=p["email"],
            role=p["role"],
            groups=p["groups"],
            last_access_raw=p["last_access_raw"],
            last_access_days=p["last_access_days"],
            status=p["status"],
        )
        for p in participants
    ]

    return ActivityResponse(
        ficha=cp["ficha"],
        course_id=cp["course_id"],
        total_active=active,
        total_suspended=suspended,
        participants=items,
    )
