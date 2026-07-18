# notes-demo

A minimal REST API for managing notes, built with Flask.

## Setup

```bash
pip install -r requirements.txt
python app.py
```

## Endpoints

### `GET /notes`

Returns all notes.

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
