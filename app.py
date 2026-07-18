import time
from collections import defaultdict
from functools import wraps

from flask import Flask, jsonify, request, abort, send_file
import os

app = Flask(__name__)

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

_notes = {}
_next_id = 1


def _make_note(title, body):
    global _next_id
    note = {"id": _next_id, "title": title, "body": body}
    _notes[_next_id] = note
    _next_id += 1
    return note


# Seed a few notes so the demo is non-empty
for _i in range(1, 6):
    _make_note(f"Note {_i}", f"Body of note {_i}.")

# ---------------------------------------------------------------------------
# Rate limiter (60 write requests per minute per IP)
# ---------------------------------------------------------------------------

RATE_LIMIT = 60          # max requests
RATE_WINDOW = 60         # seconds

# { ip: [(timestamp, count), ...] }
_rate_buckets: dict = defaultdict(list)


def _check_rate_limit(ip: str) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds).

    Uses a simple fixed-window counter reset every RATE_WINDOW seconds.
    """
    now = time.time()
    buckets = _rate_buckets[ip]

    # Drop windows that have expired
    buckets[:] = [(ts, cnt) for ts, cnt in buckets if now - ts < RATE_WINDOW]

    if not buckets:
        _rate_buckets[ip] = [(now, 1)]
        return True, 0

    window_start, count = buckets[0]
    if count >= RATE_LIMIT:
        retry_after = int(RATE_WINDOW - (now - window_start)) + 1
        return False, max(retry_after, 1)

    # Increment counter in existing window
    _rate_buckets[ip][0] = (window_start, count + 1)
    return True, 0


def rate_limited(f):
    """Decorator that enforces the write-endpoint rate limit."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        ip = request.remote_addr or "unknown"
        allowed, retry_after = _check_rate_limit(ip)
        if not allowed:
            response = jsonify({"error": "Too Many Requests"})
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response
        return f(*args, **kwargs)
    return wrapper

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/notes")
def list_notes():
    all_notes = sorted(_notes.values(), key=lambda n: n["id"])
    total = len(all_notes)

    # Parse pagination params
    try:
        limit = int(request.args.get("limit", total))
    except (ValueError, TypeError):
        abort(400, description="limit must be an integer")
    try:
        offset = int(request.args.get("offset", 0))
    except (ValueError, TypeError):
        abort(400, description="offset must be an integer")

    limit = min(max(limit, 0), 100)  # cap at 100, floor at 0
    offset = max(offset, 0)

    page = all_notes[offset: offset + limit]
    response = jsonify({"data": page})
    response.headers["X-Total-Count"] = str(total)
    return response


@app.post("/notes")
@rate_limited
def create_note():
    payload = request.get_json(silent=True) or {}
    title = payload.get("title", "")
    body = payload.get("body", "")
    if not title:
        abort(400, description="title is required")
    note = _make_note(title, body)
    return jsonify(note), 201


@app.get("/notes/<int:note_id>")
def get_note(note_id):
    note = _notes.get(note_id)
    if note is None:
        abort(404, description="Note not found")
    return jsonify(note)


@app.patch("/notes/<int:note_id>")
@rate_limited
def update_note(note_id):
    note = _notes.get(note_id)
    if note is None:
        abort(404, description="Note not found")
    payload = request.get_json(silent=True) or {}
    if "title" in payload:
        note["title"] = payload["title"]
    if "body" in payload:
        note["body"] = payload["body"]
    return jsonify(note)


@app.delete("/notes/<int:note_id>")
@rate_limited
def delete_note(note_id):
    note = _notes.pop(note_id, None)
    if note is None:
        abort(404, description="Note not found")
    return "", 204


@app.get("/openapi.yaml")
def openapi_spec():
    spec_path = os.path.join(os.path.dirname(__file__), "openapi.yaml")
    return send_file(spec_path, mimetype="application/yaml")


if __name__ == "__main__":
    app.run(debug=True)
