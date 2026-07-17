# Voucher Web App — Vercel side

This folder is a Vercel project. Right now it only has the two backend
functions; the actual HTML/CSS/JS frontend (Phase 3) will live at the
project root alongside `api/`, and Vercel serves both automatically with
no extra config.

```
webapp/
├── api/
│   ├── generate.py          # POST /api/generate
│   └── voucher-status.py    # GET  /api/voucher-status?id=...
├── requirements.txt
├── .env.example
└── (index.html etc. arrive in Phase 3)
```

## What each function does

- **`/api/generate`** — the frontend calls this when the form is submitted. It validates the input and inserts a `pending` row into Supabase's `voucher_requests` table, then immediately returns a `request_id`. It does NOT wait around for the voucher to actually be created — that's the Windows agent's job, on its own schedule.
- **`/api/voucher-status?id=...`** — the frontend polls this every couple seconds after submitting, until the row's `status` becomes `done` (or `error`), then displays the result.

Both functions hold the Supabase `service_role` key server-side only — it's never sent to the browser.

## 1. Install the Vercel CLI (for local testing)

You'll need [Node.js](https://nodejs.org) installed first (any recent LTS version). Then:

```powershell
npm install -g vercel
```

## 2. Set up local environment

```powershell
cd path\to\webapp
copy .env.example .env
notepad .env
```

Fill in your real `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` (same values your agent's `.env` already has).

## 3. Run it locally

```powershell
vercel dev
```

First run will ask a few setup questions (link to a Vercel account/project — you can create a new project here, or just accept defaults for local-only testing for now). It'll then start a local server, typically at `http://localhost:3000`.

## 4. Test both endpoints

In a **second** PowerShell window:

**Test `/api/generate`:**
```powershell
$body = @{
    name = "Test User"
    qty = 1
    expiration_minutes = 60
    byte_quota = 0
    one_time = $true
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:3000/api/generate" -Method POST -Body $body -ContentType "application/json"
```
Should return something like `{"request_id": "some-uuid"}`.

**Test `/api/voucher-status`** (use the `request_id` from above):
```powershell
Invoke-RestMethod -Uri "http://localhost:3000/api/voucher-status?id=PASTE_REQUEST_ID_HERE"
```

Right after the insert, this will show `status: pending`. If your Windows agent is running (`python app.py` in the agent folder) and polling the same Supabase project, it should pick up this request within a few seconds — re-run the status check and you should see `status: done` with a real `code`.

This proves the full chain end-to-end, all the way from a local Vercel function through Supabase to your real UniFi controller and back — without needing anything deployed yet.

## 5. When you're ready to deploy for real

Two options:

**Option A — GitHub (recommended for ongoing changes):**
1. Push this `webapp` folder to a GitHub repo
2. Vercel dashboard → Add New Project → import that repo
3. In the import screen (or after, under Project Settings → Environment Variables), add `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`
4. Deploy — every future `git push` auto-deploys

**Option B — CLI (quick, one-off):**
```powershell
vercel deploy --prod
```
Then add the two environment variables in the Vercel dashboard afterward (Project Settings → Environment Variables → redeploy to pick them up).

## Security notes

- `SUPABASE_SERVICE_KEY` goes in Vercel's environment variables (dashboard), never committed to git, never referenced in any file that ships to the browser.
- Both functions only accept the specific fields they expect and validate types before touching Supabase — malformed input gets a clear 400 error instead of crashing or passing through unchecked.
