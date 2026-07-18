# notes-demo

A minimal REST API for managing notes, built with Flask.

## Setup

```bash
pip install -r requirements.txt
python app.py
```

## Endpoints

### `GET /notes`

Returns a paginated list of all notes.

**Query parameters**

| Parameter | Type    | Default | Description                        |
|-----------|---------|---------|------------------------------------|------|
| `limit`   | integer | total   | Max notes to return (capped at 100)|
| `offset`  | integer | 0       | Notes to skip before returning     |

**Response headers**

| Header          | Description                                       |
|-----------------|---------------------------------------------------|
| `X-Total-Count` | Total number of notes in the collection (unpaged) |

### `POST /notes`

Create a note. Body: `{"title": "...", "body": "..."}` (`title` required).

### `GET /notes/:id`

Retrieve a single note.

### `PATCH /notes/:id`

Update `title` and/or `body` of a note.

### `DELETE /notes/:id`

Delete a note.

### `GET /openapi.yaml`

Returns the OpenAPI 3.1 specification for this API.

## Rate limiting

Write endpoints (`POST`, `PATCH`, `DELETE`) are throttled to **60 requests per minute per IP**.
Requests that exceed this limit receive `429 Too Many Requests` with a `Retry-After` header
indicating how many seconds to wait before retrying.

## Tests

```bash
pytest
```
