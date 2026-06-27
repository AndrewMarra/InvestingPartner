import sqlite3, tempfile
from aiportfolio.multiuser.users import UserStore


def test_pause_excludes_from_active_but_not_all():
    db = tempfile.mktemp(suffix=".db")
    s = UserStore(db)
    a = s.add_user("a@x.com", "+1")
    b = s.add_user("b@x.com", "+2")
    s.set_paused(a, True)
    active_ids = {u["id"] for u in s.list_active()}
    all_ids = {u["id"] for u in s.list_all()}
    assert a not in active_ids and b in active_ids   # runner skips paused
    assert a in all_ids and b in all_ids             # admin still sees both
    s.set_paused(a, False)
    assert a in {u["id"] for u in s.list_active()}    # resume puts them back


def test_paused_column_migrated_onto_old_db():
    db = tempfile.mktemp(suffix=".db")
    # Simulate a pre-pause DB: users table without the `paused` column.
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT UNIQUE, phone TEXT, "
                 "active INTEGER DEFAULT 1, created_at TEXT)")
    conn.execute("INSERT INTO users (id, email, phone, active) VALUES ('u1','a@x.com','+1',1)")
    conn.commit(); conn.close()
    s = UserStore(db)  # __init__ should ALTER TABLE to add paused
    assert {u["id"] for u in s.list_active()} == {"u1"}
    s.set_paused("u1", True)
    assert s.list_active() == []
