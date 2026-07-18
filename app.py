"""
app.py

Single FastAPI app, deployed as one Vercel Function, handling both
routes for the voucher web app:

    POST /api/generate          -- insert a pending voucher request
    GET  /api/voucher-status    -- poll for the result

Required Vercel environment variables (Project Settings -> Environment Variables):
    SUPABASE_URL
    SUPABASE_SERVICE_KEY   (the "service_role" key -- secret, server-side only)
"""

import os
from typing import Optional, Union

import requests
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

app = FastAPI()

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")


def require_config():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise HTTPException(500, "Server misconfigured: missing Supabase env vars")


def write_headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY or ''}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def read_headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY or ''}",
    }


class VoucherRequest(BaseModel):
    name: Optional[str] = ""
    qty: int
    expiration_minutes: int
    down_limit_kbps: Optional[int] = None
    up_limit_kbps: Optional[int] = None
    byte_quota: Union[str, int, float]
    one_time: bool


@app.post("/api/generate")
def generate(req: VoucherRequest):
    require_config()

    payload = {
        "name": (req.name or "")[:200],
        "qty": req.qty,
        "expiration_minutes": req.expiration_minutes,
        "down_limit_kbps": req.down_limit_kbps,
        "up_limit_kbps": req.up_limit_kbps,
        "byte_quota": str(req.byte_quota),
        "one_time": req.one_time,
        "status": "pending",
    }

    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/voucher_requests",
            headers=write_headers(),
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(502, f"Could not reach Supabase: {e}")

    rows = resp.json()
    if not rows:
        raise HTTPException(502, "Insert succeeded but no row was returned")

    return {"request_id": rows[0]["id"]}


@app.get("/api/voucher-status")
def voucher_status(id: str = Query(...)):
    require_config()

    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/voucher_requests",
            headers=read_headers(),
            params={
                "id": f"eq.{id}",
                "select": "status,code,error_message,voucher_data,created_at,completed_at",
            },
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(502, f"Could not reach Supabase: {e}")

    rows = resp.json()
    if not rows:
        raise HTTPException(404, "Request not found")

    return rows[0]
