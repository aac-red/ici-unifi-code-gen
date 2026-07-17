"""
api/generate.py

POST /api/generate

Accepts a voucher request from the frontend, validates it, and inserts a
"pending" row into Supabase. The Windows agent picks it up on its next
poll cycle and fills in the result. This function returns immediately
with the new row's id -- it does NOT wait for the voucher to be created.
The frontend polls /api/voucher-status with that id to get the result.

Required Vercel environment variables (Project Settings -> Environment Variables):
    SUPABASE_URL
    SUPABASE_SERVICE_KEY   (the "service_role" key -- secret, server-side only,
                             never expose this in frontend/browser code)
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import requests

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SUPABASE_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY or "",
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY or ''}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            return self._send_json(500, {"error": "Server misconfigured: missing Supabase env vars"})

        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._send_json(400, {"error": "Invalid JSON body"})

        try:
            payload = self._build_payload(body)
        except (KeyError, ValueError, TypeError) as e:
            return self._send_json(400, {"error": f"Invalid input: {e}"})

        try:
            resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/voucher_requests",
                headers=SUPABASE_HEADERS,
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            return self._send_json(502, {"error": f"Could not reach Supabase: {e}"})

        rows = resp.json()
        if not rows:
            return self._send_json(502, {"error": "Insert succeeded but no row was returned"})

        return self._send_json(200, {"request_id": rows[0]["id"]})

    @staticmethod
    def _build_payload(body):
        for field in ("qty", "expiration_minutes", "byte_quota", "one_time"):
            if field not in body:
                raise KeyError(f"missing field '{field}'")

        return {
            "name": str(body.get("name") or "")[:200],
            "qty": int(body["qty"]),
            "expiration_minutes": int(body["expiration_minutes"]),
            "down_limit_kbps": int(body["down_limit_kbps"]) if body.get("down_limit_kbps") else None,
            "up_limit_kbps": int(body["up_limit_kbps"]) if body.get("up_limit_kbps") else None,
            "byte_quota": str(body["byte_quota"]),
            "one_time": bool(body["one_time"]),
            "status": "pending",
        }

    def _send_json(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
