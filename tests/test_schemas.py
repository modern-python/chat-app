import uuid

import pydantic
import pytest

from app.schemas.api import Collection, EditMessageRequest, SendMessageRequest, User
from tests.factories import UserFactory


def test_collection_builds_from_models() -> None:
    user = UserFactory.build(id=1, username="alice", display_name="Alice")
    collection = Collection[User].from_models([user])
    assert collection.items == [User(id=1, username="alice", display_name="Alice")]


def _build_message_request(
    model: type[SendMessageRequest | EditMessageRequest], text: str
) -> SendMessageRequest | EditMessageRequest:
    if model is SendMessageRequest:
        return SendMessageRequest(idempotency_key=uuid.uuid4(), text=text)
    return EditMessageRequest(text=text)


@pytest.mark.parametrize("model", [SendMessageRequest, EditMessageRequest])
@pytest.mark.parametrize("text", ["", "x" * 4001], ids=["empty", "over_max"])
def test_message_request_rejects_out_of_bounds_text(
    model: type[SendMessageRequest | EditMessageRequest], text: str
) -> None:
    with pytest.raises(pydantic.ValidationError):
        _build_message_request(model, text)


@pytest.mark.parametrize("model", [SendMessageRequest, EditMessageRequest])
def test_message_request_accepts_max_length_text(model: type[SendMessageRequest | EditMessageRequest]) -> None:
    text = "x" * 4000
    assert _build_message_request(model, text).text == text
