# Booking Agent — Custom API Agent (AMP Test Day, T8)

A plain FastAPI REST service (no MCP, no chat) for testing AMP's **Custom API
Agent** path: OpenAPI-described endpoints on a non-default port, a file
mount, and a secret-sourced environment variable.

## Endpoints

- `GET /health`
- `GET /policy` — returns the cancellation policy read from the file-mounted path
- `POST /bookings` — create a booking; also generates a one-line confirmation
  message via OpenAI if `OPENAI_API_KEY` is set (falls back to a template
  otherwise), so a deployed booking produces an LLM span for tracing/eval
- `GET /bookings?user_id=...` — list bookings for a user
- `GET /bookings/{booking_id}?user_id=...`
- `PUT /bookings/{booking_id}`
- `DELETE /bookings/{booking_id}?user_id=...` — cancel

Bookings are held in memory for the life of the process (reset on restart) —
the deployed container runs a read-only root filesystem, so this intentionally
avoids writing to disk.

## Local run

```bash
cd custom-api-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optionally add OPENAI_API_KEY
python main.py
curl http://localhost:8085/health
```

## Deploying on the AMP console — field mapping

When creating the agent (**New Agent → Create → Source**, this repo/branch):

| Field | Value |
|---|---|
| Interface Type | **Custom API Agent** |
| Language | **Python** |
| Project Path | `custom-api-agent` (this is a subfolder of the repo) |
| Start Command | `python main.py` |
| OpenAPI Spec Path | `/custom-api-agent/openapi.yaml` (repo-relative) |
| Port | `8085` |
| Base Path | `/` |

**File mount** (Phase 1 step 2): add one file —
- File Name: `cancellation-policy.txt`
- Mount Path: `/etc/config/cancellation-policy.txt`
- File Content: paste the contents of `sample-config/cancellation-policy.txt`

This matches the app's default `POLICY_FILE_PATH`, so `GET /policy` and the
`cancellation_policy` field in a booking response will reflect the mounted
file instead of the code's fallback text — a good way to confirm the mount
actually landed in the running container.

**Secret-sourced environment variable** (Phase 1 step 2): add
`OPENAI_API_KEY`, mark it secret, value = your assigned OpenAI key. Without
it the agent still works — bookings just get a templated confirmation
message instead of an LLM-generated one, so this is easy to verify by
toggling the var and re-testing `POST /bookings`.

## Verifying after deploy

- `Try It` should render a Swagger UI (this confirms `Custom API Agent` +
  the OpenAPI spec path were honored, not a chat box).
- `POST /bookings` with a body like:
  ```json
  {
    "user_id": "guest-1",
    "check_in_date": "2026-09-01",
    "check_out_date": "2026-09-03",
    "number_of_guests": 2,
    "primary_guest": {"name": "Jane Doe"}
  }
  ```
  should return a `confirmation_message` and `cancellation_policy` — check
  the trace view for an LLM span if `OPENAI_API_KEY` was set.
