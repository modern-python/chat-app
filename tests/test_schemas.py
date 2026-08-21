from app.schemas.api import Collection, User
from tests.factories import UserFactory


def test_collection_builds_from_models() -> None:
    user = UserFactory.build(id=1, username="alice", display_name="Alice")
    collection = Collection[User].from_models([user])
    assert collection.items == [User(id=1, username="alice", display_name="Alice")]
