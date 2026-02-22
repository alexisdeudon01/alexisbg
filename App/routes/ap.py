from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from services.ap_control import get_ap_status, update_ssid, update_password, stop_ap, start_ap

router = APIRouter(prefix="/api/ap", tags=["access_point"])


class APUpdateRequest(BaseModel):
    ssid: Optional[str] = None
    password: Optional[str] = None


@router.get("/status")
async def ap_status():
    return get_ap_status()


@router.post("/update")
async def ap_update(req: APUpdateRequest):
    results = {}
    if req.ssid:
        results["ssid"] = update_ssid(req.ssid)
    if req.password:
        results["password"] = update_password(req.password)
    if not req.ssid and not req.password:
        return {"error": "Provide ssid or password"}
    return results


@router.post("/stop")
async def ap_stop():
    return stop_ap()


@router.post("/start")
async def ap_start():
    return start_ap()
