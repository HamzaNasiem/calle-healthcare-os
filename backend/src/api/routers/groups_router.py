from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ...core.database import supabase, supabase_read
from ...core.security import get_current_user_with_role, AuthenticatedUser

router = APIRouter(prefix="/groups", tags=["Clinic Groups"])


# -----------------------------------------------------------------------------
# Pydantic Models
# -----------------------------------------------------------------------------

class GroupCreate(BaseModel):
    name: str
    owner_email: str


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    stripe_customer_id: Optional[str] = None


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _verify_group_owner(group_id: str, auth: AuthenticatedUser) -> dict:
    """Fetch a clinic_group by id and verify that owner_email matches auth.email.
    Raises HTTPException 404/403 on failure. Returns the group dict on success."""
    res = supabase_read.table("clinic_groups").select("*").eq("id", group_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Group not found")
    group = res.data[0]
    if group.get("owner_email") != auth.email:
        raise HTTPException(status_code=403, detail="Access denied: you do not own this group")
    return group


def _verify_clinic_owner(clinic_id: str, auth: AuthenticatedUser) -> dict:
    """Fetch a clinic by id and verify owner_email matches auth.email.
    Raises HTTPException 404/403 on failure. Returns the clinic dict on success."""
    res = supabase_read.table("clinics").select("*").eq("id", clinic_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Clinic not found")
    clinic = res.data[0]
    if clinic.get("owner_email") != auth.email:
        raise HTTPException(status_code=403, detail="Access denied: you do not own this clinic")
    return clinic


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.post("", status_code=201)
async def create_group(
    group: GroupCreate,
    auth: AuthenticatedUser = Depends(get_current_user_with_role),
):
    """Create a new clinic group. Owner role required."""
    import asyncio

    try:
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("clinic_groups").insert(group.model_dump()).execute(),
        )
        return {"data": res.data[0]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_groups(
    auth: AuthenticatedUser = Depends(get_current_user_with_role),
):
    """List all clinic groups owned by the authenticated user."""
    import asyncio

    try:
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("clinic_groups")
            .select("*")
            .eq("owner_email", auth.email)
            .execute(),
        )
        return {"data": res.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{group_id}")
async def get_group(
    group_id: str,
    auth: AuthenticatedUser = Depends(get_current_user_with_role),
):
    """Get a single clinic group along with all clinics belonging to it."""
    import asyncio

    try:
        group = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _verify_group_owner(group_id, auth)
        )

        clinics_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("clinics")
            .select("*")
            .eq("group_id", group_id)
            .execute(),
        )

        return {"data": {**group, "clinics": clinics_res.data}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{group_id}/add-clinic/{clinic_id}")
async def add_clinic_to_group(
    group_id: str,
    clinic_id: str,
    auth: AuthenticatedUser = Depends(get_current_user_with_role),
):
    """Add a clinic to a group. Both the group and the clinic must be owned by the auth user."""
    import asyncio

    try:
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: _verify_group_owner(group_id, auth)
        )

        await asyncio.get_event_loop().run_in_executor(
            None, lambda: _verify_clinic_owner(clinic_id, auth)
        )

        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("clinics")
            .update({"group_id": group_id})
            .eq("id", clinic_id)
            .execute(),
        )
        return {"data": res.data[0] if res.data else {"clinic_id": clinic_id, "group_id": group_id}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{group_id}/remove-clinic/{clinic_id}")
async def remove_clinic_from_group(
    group_id: str,
    clinic_id: str,
    auth: AuthenticatedUser = Depends(get_current_user_with_role),
):
    """Remove a clinic from a group (sets group_id to NULL on the clinic row)."""
    import asyncio

    try:
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: _verify_group_owner(group_id, auth)
        )

        clinic = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _verify_clinic_owner(clinic_id, auth)
        )
        if clinic.get("group_id") != group_id:
            raise HTTPException(
                status_code=400,
                detail="Clinic does not belong to the specified group",
            )

        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("clinics")
            .update({"group_id": None})
            .eq("id", clinic_id)
            .execute(),
        )
        return {"data": res.data[0] if res.data else {"clinic_id": clinic_id, "group_id": None}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{group_id}/patients")
async def get_group_patients(
    group_id: str,
    auth: AuthenticatedUser = Depends(get_current_user_with_role),
):
    """Cross-location patient lookup: returns all patients across every clinic in
    the group, enriched with a clinic_name field."""
    import asyncio

    try:
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: _verify_group_owner(group_id, auth)
        )

        clinics_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("clinics")
            .select("id, name")
            .eq("group_id", group_id)
            .execute(),
        )
        clinics = clinics_res.data or []
        if not clinics:
            return {"data": []}

        clinic_map = {c["id"]: c["name"] for c in clinics}
        clinic_ids = list(clinic_map.keys())

        patients_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("patients")
            .select("*")
            .in_("clinic_id", clinic_ids)
            .execute(),
        )
        patients = patients_res.data or []

        for patient in patients:
            patient["clinic_name"] = clinic_map.get(patient.get("clinic_id"), "Unknown")

        return {"data": patients}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{group_id}/stats")
async def get_group_stats(
    group_id: str,
    auth: AuthenticatedUser = Depends(get_current_user_with_role),
):
    """Aggregate stats across all clinics in the group:
    total_calls, total_appointments, total_revenue_cents."""
    import asyncio

    try:
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: _verify_group_owner(group_id, auth)
        )

        clinics_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("clinics")
            .select("id")
            .eq("group_id", group_id)
            .execute(),
        )
        clinics = clinics_res.data or []
        if not clinics:
            return {"data": {"total_calls": 0, "total_appointments": 0, "total_revenue_cents": 0}}

        clinic_ids = [c["id"] for c in clinics]

        calls_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("calls")
            .select("id", count="exact")
            .in_("clinic_id", clinic_ids)
            .execute(),
        )

        appts_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("appointments")
            .select("id", count="exact")
            .in_("clinic_id", clinic_ids)
            .execute(),
        )

        revenue_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase_read.table("revenue_events")
            .select("amount_cents")
            .in_("clinic_id", clinic_ids)
            .execute(),
        )
        revenue_data = revenue_res.data or []
        total_revenue_cents = sum(r.get("amount_cents", 0) or 0 for r in revenue_data)

        return {
            "data": {
                "total_calls": calls_res.count or len(calls_res.data or []),
                "total_appointments": appts_res.count or len(appts_res.data or []),
                "total_revenue_cents": total_revenue_cents,
                "clinic_count": len(clinic_ids),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
