import pytest
from app import app, _notes, _make_note


@pytest.fixture(autouse=True)
def reset_store():
    """Reset the in-memory store before each test."""
    _notes.clear()
    import app as app_module
    app_module._next_id = 1
    yield


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def seed(n=5):
    for i in range(1, n + 1):
        _make_note(f"Note {i}", f"Body {i}")


# ---------------------------------------------------------------------------
# GET /notes – pagination
# ---------------------------------------------------------------------------

class TestListNotesPagination:
    def test_defaults_return_all_when_few_notes(self, client):
        seed(3)
        rv = client.get("/notes")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["page"] == 1
        assert data["per_page"] == 20
        assert data["total"] == 3
        assert len(data["data"]) == 3

    def test_default_page_is_1(self, client):
        seed(3)
        rv = client.get("/notes?per_page=10")
        assert rv.get_json()["page"] == 1

    def test_default_per_page_is_20(self, client):
        seed(3)
        rv = client.get("/notes?page=1")
        assert rv.get_json()["per_page"] == 20

    def test_pagination_slices_correctly(self, client):
        seed(10)
        rv = client.get("/notes?page=2&per_page=3")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["page"] == 2
        assert data["per_page"] == 3
        assert data["total"] == 10
        assert len(data["data"]) == 3
        # page 2, per_page 3 → items 4,5,6
        assert [n["id"] for n in data["data"]] == [4, 5, 6]

    def test_last_page_may_have_fewer_items(self, client):
        seed(7)
        rv = client.get("/notes?page=2&per_page=5")
        data = rv.get_json()
        assert data["total"] == 7
        assert len(data["data"]) == 2  # only 2 remain on page 2

    def test_beyond_last_page_returns_empty_data(self, client):
        seed(5)
        rv = client.get("/notes?page=99&per_page=10")
        data = rv.get_json()
        assert rv.status_code == 200
        assert data["data"] == []
        assert data["total"] == 5

    def test_per_page_1(self, client):
        seed(5)
        rv = client.get("/notes?page=1&per_page=1")
        data = rv.get_json()
        assert len(data["data"]) == 1
        assert data["data"][0]["id"] == 1

    def test_per_page_max_100(self, client):
        seed(5)
        rv = client.get("/notes?per_page=100")
        assert rv.status_code == 200

    def test_per_page_above_100_rejected(self, client):
        rv = client.get("/notes?per_page=101")
        assert rv.status_code == 400

    def test_per_page_zero_rejected(self, client):
        rv = client.get("/notes?per_page=0")
        assert rv.status_code == 400

    def test_page_zero_rejected(self, client):
        rv = client.get("/notes?page=0")
        assert rv.status_code == 400

    def test_non_integer_page_rejected(self, client):
        rv = client.get("/notes?page=abc")
        assert rv.status_code == 400

    def test_non_integer_per_page_rejected(self, client):
        rv = client.get("/notes?per_page=abc")
        assert rv.status_code == 400

    def test_response_includes_pagination_metadata(self, client):
        seed(3)
        data = client.get("/notes?page=1&per_page=2").get_json()
        assert "page" in data
        assert "per_page" in data
        assert "total" in data
        assert "data" in data


# ---------------------------------------------------------------------------
# Basic CRUD sanity checks
# ---------------------------------------------------------------------------

class TestCRUD:
    def test_create_and_retrieve(self, client):
        rv = client.post("/notes", json={"title": "Hello", "body": "World"})
        assert rv.status_code == 201
        note = rv.get_json()
        assert note["id"] == 1
        rv2 = client.get(f"/notes/{note['id']}")
        assert rv2.status_code == 200
        assert rv2.get_json()["title"] == "Hello"

    def test_create_requires_title(self, client):
        rv = client.post("/notes", json={"body": "No title"})
        assert rv.status_code == 400

    def test_update_note(self, client):
        client.post("/notes", json={"title": "Old", "body": ""})
        rv = client.patch("/notes/1", json={"title": "New"})
        assert rv.status_code == 200
        assert rv.get_json()["title"] == "New"

    def test_delete_note(self, client):
        client.post("/notes", json={"title": "Bye", "body": ""})
        rv = client.delete("/notes/1")
        assert rv.status_code == 204
        assert client.get("/notes/1").status_code == 404
