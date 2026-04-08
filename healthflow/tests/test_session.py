from healthflow.memory.session import InMemoryStore


def test_save_and_load():
    store = InMemoryStore()
    store.save("session-1", {"zip_code": "10001", "plans": []})
    result = store.load("session-1")
    assert result is not None
    assert result["zip_code"] == "10001"


def test_load_nonexistent():
    store = InMemoryStore()
    result = store.load("nonexistent")
    assert result is None


def test_overwrite_session():
    store = InMemoryStore()
    store.save("session-1", {"version": 1})
    store.save("session-1", {"version": 2})
    result = store.load("session-1")
    assert result["version"] == 2


def test_multiple_sessions():
    store = InMemoryStore()
    store.save("s1", {"data": "first"})
    store.save("s2", {"data": "second"})
    assert store.load("s1")["data"] == "first"
    assert store.load("s2")["data"] == "second"
