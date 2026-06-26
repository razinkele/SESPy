from sespy import feedback_store


def test_add_and_get(tmp_path):
    db = tmp_path / "fb.db"
    fid = feedback_store.add("It froze on export", 2, "bug", db_path=db)
    assert isinstance(fid, int) and fid >= 1
    row = feedback_store.get(fid, db_path=db)
    assert row["message"] == "It froze on export"
    assert row["rating"] == 2
    assert row["category"] == "bug"
    assert row["status"] == "open"
    assert row["created_at"]  # ISO timestamp present


def test_list_entries_newest_first(tmp_path):
    db = tmp_path / "fb.db"
    feedback_store.add("first", 3, "general", db_path=db)
    feedback_store.add("second", 5, "suggestion", db_path=db)
    rows = feedback_store.list_entries(db_path=db)
    assert [r["message"] for r in rows] == ["second", "first"]


def test_db_path_honors_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SESPY_FEEDBACK_DB", str(tmp_path / "envfb.db"))
    assert feedback_store.db_path() == tmp_path / "envfb.db"


def test_connect_creates_missing_dir(tmp_path):
    nested = tmp_path / "logs" / "feedback.db"   # parent does not exist yet
    fid = feedback_store.add("x", 1, "bug", db_path=nested)
    assert nested.exists() and fid >= 1
