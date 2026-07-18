# notes-demo

A minimal REST API for managing notes, built with Flask.

## Setup

```bash
pip install -r requirements.txt
python app.py
```

## Endpoints

### `GET /notes`

Returns a paginated list of notes.

| Query param | Default | Constraints | Description |
|---|---|---|---|
| `page` | `1` | `>= 1` | Page number (1-based) |
| `per_page` | `20` | `1 – 100` | Items per page |

**Response**

```json
{
  "data": [{"id": 1, "title": "Note 1", "body": "Body of note 1."}],
  "page": 1,
  "per_page": 20,
  "total": 5
}
```

### `POST /notes`

Create a note. Body: `{"title": "...", "body": "..."}` (`title` required).

### `GET /notes/:id`

Retrieve a single note.

### `PATCH /notes/:id`

Update `title` and/or `body` of a note.

### `DELETE /notes/:id`

Delete a note.

## Tests

```bash
pytest
```
