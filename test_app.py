"""Tests for the Notes API."""
import importlib
import sys
import time
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fresh_app():
    """Re-import app before every test to get a clean in-memory store."""
    # Remove cached module so module-level state is reset
    for mod in list(sys.modules.keys()):
        if mod == "app":
            del sys.modules[mod]
    import app as app_module
    yield app_module
    # Clean up after test
    for mod in list(sys.modules.keys()):
        if mod == "app":
            del sys.modules[mod]


@pytest.fixture()
def client(fresh_app):
    fresh_app.app.config["TESTING"] = True
    with fresh_app.app.test_client() as c:
        yield c

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_note(client, title="Test", body="Body"):
    return client.post("/notes", json={"title": title, "body": body})


# ---------------------------------------------------------------------------
# GET /notes – basic
# ---------------------------------------------------------------------------

class TestListNotes:
    def test_returns_seeded_notes(self, client):
        r = client.get("/notes")
        assert r.status_code == 200
        data = r.get_json()
        assert "data" in data
        assert len(data["data"]) == 5   # 5 seeded notes

    def test_x_total_count_header(self, client):
        r = client.get("/notes")
        assert "X-Total-Count" in r.headers
        assert r.headers["X-Total-Count"] == "5"

    def test_notes_sorted_by_id(self, client):
        r = client.get("/notes")
        ids = [n["id"] for n in r.get_json()["data"]]
        assert ids == sorted(ids)

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def test_limit_param(self, client):
        r = client.get("/notes?limit=2")
        assert r.status_code == 200
        data = r.get_json()
        assert len(data["data"]) == 2

    def test_offset_param(self, client):
        r_all = client.get("/notes")
        all_ids = [n["id"] for n in r_all.get_json()["data"]]

        r = client.get("/notes?offset=2")
        page_ids = [n["id"] for n in r.get_json()["data"]]
        assert page_ids == all_ids[2:]

    def test_limit_and_offset(self, client):
        r_all = client.get("/notes")
        all_ids = [n["id"] for n in r_all.get_json()["data"]]

        r = client.get("/notes?limit=2&offset=1")
        assert r.status_code == 200
        page_ids = [n["id"] for n in r.get_json()["data"]]
        assert page_ids == all_ids[1:3]

    def test_limit_capped_at_100(self, client, fresh_app):
        # Insert notes directly to avoid hitting the rate limiter
        for i in range(100):
            fresh_app._make_note(f"Extra {i}", "body")
        r = client.get("/notes?limit=200")
        assert r.status_code == 200
        assert len(r.get_json()["data"]) == 100

    def test_x_total_count_reflects_full_collection(self, client):
        r = client.get("/notes?limit=2")
        assert r.headers["X-Total-Count"] == "5"

    def test_invalid_limit_returns_400(self, client):
        r = client.get("/notes?limit=abc")
        assert r.status_code == 400

    def test_invalid_offset_returns_400(self, client):
        r = client.get("/notes?offset=xyz")
        assert r.status_code == 400

    def test_offset_beyond_total_returns_empty(self, client):
        r = client.get("/notes?offset=100")
        assert r.status_code == 200
        assert r.get_json()["data"] == []

    def test_limit_zero_returns_empty(self, client):
        r = client.get("/notes?limit=0")
        assert r.status_code == 200
        assert r.get_json()["data"] == []


# ---------------------------------------------------------------------------
# POST /notes
# ---------------------------------------------------------------------------

class TestCreateNote:
    def test_creates_note(self, client):
        r = client.post("/notes", json={"title": "My note", "body": "hello"})
        assert r.status_code == 201
        note = r.get_json()
        assert note["title"] == "My note"
        assert note["body"] == "hello"
        assert "id" in note

    def test_missing_title_returns_400(self, client):
        r = client.post("/notes", json={"body": "no title"})
        assert r.status_code == 400

    def test_empty_body_allowed(self, client):
        r = client.post("/notes", json={"title": "No body"})
        assert r.status_code == 201

    def test_note_appears_in_list(self, client):
        client.post("/notes", json={"title": "Listed", "body": "yes"})
        r = client.get("/notes")
        titles = [n["title"] for n in r.get_json()["data"]]
        assert "Listed" in titles


# ---------------------------------------------------------------------------
# GET /notes/<id>
# ---------------------------------------------------------------------------

class TestGetNote:
    def test_get_existing(self, client):
        r = client.get("/notes/1")
        assert r.status_code == 200
        assert r.get_json()["id"] == 1

    def test_get_missing_returns_404(self, client):
        r = client.get("/notes/9999")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /notes/<id>
# ---------------------------------------------------------------------------

class TestUpdateNote:
    def test_update_title(self, client):
        r = client.patch("/notes/1", json={"title": "Updated"})
        assert r.status_code == 200
        assert r.get_json()["title"] == "Updated"

    def test_update_body(self, client):
        r = client.patch("/notes/1", json={"body": "new body"})
        assert r.status_code == 200
        assert r.get_json()["body"] == "new body"

    def test_partial_update_preserves_fields(self, client):
        original = client.get("/notes/1").get_json()
        client.patch("/notes/1", json={"body": "changed"})
        updated = client.get("/notes/1").get_json()
        assert updated["title"] == original["title"]
        assert updated["body"] == "changed"

    def test_update_missing_returns_404(self, client):
        r = client.patch("/notes/9999", json={"title": "x"})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /notes/<id>
# ---------------------------------------------------------------------------

class TestDeleteNote:
    def test_delete_existing(self, client):
        r = client.delete("/notes/1")
        assert r.status_code == 204

    def test_deleted_note_not_found(self, client):
        client.delete("/notes/1")
        r = client.get("/notes/1")
        assert r.status_code == 404

    def test_delete_missing_returns_404(self, client):
        r = client.delete("/notes/9999")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    """Verify that write endpoints enforce the 60 req/min limit per IP."""

    def _exhaust_limit(self, client, import_module):
        """Send RATE_LIMIT requests through the rate limiter bucket directly."""
        # Manipulate the internal bucket so the next request is over the limit
        ip = "127.0.0.1"
        import_module._rate_buckets[ip] = [(time.time(), import_module.RATE_LIMIT)]

    def test_post_rate_limited(self, client, fresh_app):
        self._exhaust_limit(client, fresh_app)
        r = client.post("/notes", json={"title": "x"})
        assert r.status_code == 429

    def test_patch_rate_limited(self, client, fresh_app):
        self._exhaust_limit(client, fresh_app)
        r = client.patch("/notes/1", json={"title": "x"})
        assert r.status_code == 429

    def test_delete_rate_limited(self, client, fresh_app):
        self._exhaust_limit(client, fresh_app)
        r = client.delete("/notes/1")
        assert r.status_code == 429

    def test_retry_after_header_present(self, client, fresh_app):
        self._exhaust_limit(client, fresh_app)
        r = client.post("/notes", json={"title": "x"})
        assert "Retry-After" in r.headers
        assert int(r.headers["Retry-After"]) >= 1

    def test_get_not_rate_limited(self, client, fresh_app):
        """GET /notes must never be rate-limited."""
        self._exhaust_limit(client, fresh_app)
        r = client.get("/notes")
        assert r.status_code == 200

    def test_get_note_not_rate_limited(self, client, fresh_app):
        self._exhaust_limit(client, fresh_app)
        r = client.get("/notes/1")
        assert r.status_code == 200

    def test_requests_under_limit_succeed(self, client):
        """First 60 write requests from an IP should all succeed."""
        for i in range(60):
            r = client.post("/notes", json={"title": f"note {i}"})
            assert r.status_code == 201

    def test_rate_limit_window_resets(self, client, fresh_app):
        """After the window expires the bucket should allow requests again."""
        ip = "127.0.0.1"
        # Place the bucket in the past (window expired)
        fresh_app._rate_buckets[ip] = [(time.time() - fresh_app.RATE_WINDOW - 1, fresh_app.RATE_LIMIT)]
        r = client.post("/notes", json={"title": "after reset"})
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# GET /openapi.yaml
# ---------------------------------------------------------------------------

class TestOpenAPISpec:
    def test_spec_served(self, client):
        r = client.get("/openapi.yaml")
        assert r.status_code == 200

    def test_spec_content_type(self, client):
        r = client.get("/openapi.yaml")
        assert "yaml" in r.content_type.lower()

    def test_spec_contains_openapi_key(self, client):
        r = client.get("/openapi.yaml")
        assert b"openapi" in r.data

    def test_spec_contains_notes_paths(self, client):
        r = client.get("/openapi.yaml")
        content = r.data.decode()
        assert "/notes" in content
