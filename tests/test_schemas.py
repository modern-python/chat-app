from app.schemas.api import Collection, User


def test_collection_builds_from_models() -> None:
    collection = Collection[User].from_models([{"id": 1, "username": "alice", "display_name": "Alice"}])
    assert collection.items == [User(id=1, username="alice", display_name="Alice")]
