import sqlite3, tempfile
from aiportfolio.multiuser import crypto
from aiportfolio.multiuser.users import UserStore


def test_encrypt_roundtrip():
    ct = crypto.encrypt("secret-value-123")
    assert ct != "secret-value-123"
    assert crypto.decrypt(ct) == "secret-value-123"


def test_keys_stored_as_ciphertext():
    db = tempfile.mktemp(suffix=".db")
    s = UserStore(db)
    uid = s.add_user("a@x.com", "+15551110000")
    s.set_keys(uid, {"anthropic_key": "sk-PLAINTEXT", "alpaca_key": "PK-PLAINTEXT"})
    raw = sqlite3.connect(db).execute("SELECT ciphertext FROM user_keys").fetchall()
    assert all("PLAINTEXT" not in r[0] for r in raw)
    assert s.get_keys(uid)["anthropic_key"] == "sk-PLAINTEXT"


def test_user_isolation():
    db = tempfile.mktemp(suffix=".db")
    s = UserStore(db)
    a = s.add_user("a@x.com", "+1"); b = s.add_user("b@x.com", "+2")
    s.set_keys(a, {"anthropic_key": "A"}); s.set_keys(b, {"anthropic_key": "B"})
    assert s.get_keys(a)["anthropic_key"] == "A"
    assert s.get_keys(b)["anthropic_key"] == "B"
    assert len(s.list_active()) == 2


def test_settings_roundtrip():
    db = tempfile.mktemp(suffix=".db")
    s = UserStore(db)
    uid = s.add_user("a@x.com", "+1")
    s.set_settings(uid, {"modes": {"enabled": ["equity_day"]}})
    assert s.get_settings(uid)["modes"]["enabled"] == ["equity_day"]
