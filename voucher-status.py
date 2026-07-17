"""
api/voucher-status.py

GET /api/voucher-status?id=<request_id>

The frontend polls this after submitting a request, every couple seconds,
until status is "done" (or "error"). Returns the current row's status,
code, and any error message directly from Supabase.

Required Vercel environment variables:
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
"""

from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import urlparse, parse_qs
import requests

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SUPABASE_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY or "",
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY or ''}",
}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            return self._send_json(500, {"error": "Server misconfigured: missing Supabase env vars"})

        query = parse_qs(urlparse(self.path).query)
        request_id = (query.get("id") or [None])[0]
        if not request_id:
            return self._send_json(400, {"error": "Missing 'id' query parameter"})

        try:
            resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/voucher_requests",
                headers=SUPABASE_HEADERS,
                params={
                    "id": f"eq.{request_id}",
                    "select": "status,code,error_message,voucher_data,created_at,completed_at",
                },
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            return self._send_json(502, {"error": f"Could not reach Supabase: {e}"})

        rows = resp.json()
        if not rows:
            return self._send_json(404, {"error": "Request not found"})

        return self._send_json(200, rows[0])

    def _send_json(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
