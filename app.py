from flask import Flask, jsonify, request, abort

app = Flask(__name__)

# In-memory store
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


@app.get("/notes")
def list_notes():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except (TypeError, ValueError):
        abort(400, description="page and per_page must be integers")

    if page < 1:
        abort(400, description="page must be >= 1")
    if not (1 <= per_page <= 100):
        abort(400, description="per_page must be between 1 and 100")

    all_notes = sorted(_notes.values(), key=lambda n: n["id"])
    total = len(all_notes)
    start = (page - 1) * per_page
    end = start + per_page
    items = all_notes[start:end]

    return jsonify(
        {
            "data": items,
            "page": page,
            "per_page": per_page,
            "total": total,
        }
    )


@app.post("/notes")
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
def delete_note(note_id):
    note = _notes.pop(note_id, None)
    if note is None:
        abort(404, description="Note not found")
    return "", 204


if __name__ == "__main__":
    app.run(debug=True)
