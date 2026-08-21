import datetime
import uuid
from collections.abc import Iterable
from typing import Any, Self

import pydantic
from pydantic import BaseModel, PositiveInt

from app.database import tables


class Base(BaseModel):
    model_config = pydantic.ConfigDict(from_attributes=True)


class Collection[T: Base](Base):
    items: list[T]

    @classmethod
    def from_models(cls, objects: Iterable[Any]) -> Self:
        return cls.model_validate({"items": list(objects)})


class RegisterRequest(Base):
    username: str = pydantic.Field(min_length=3, max_length=64)
    password: str = pydantic.Field(min_length=8, max_length=128)
    display_name: str = pydantic.Field(min_length=1, max_length=128)


class LoginRequest(Base):
    username: str
    password: str


class User(Base):
    id: PositiveInt
    username: str
    display_name: str


class CreateChatRequest(Base):
    chat_type: tables.ChatType
    member_ids: list[PositiveInt] = pydantic.Field(min_length=1)
    title: str | None = pydantic.Field(default=None, max_length=128)


class ChatMember(Base):
    user_id: PositiveInt
    last_read_message_id: PositiveInt | None = None


class MarkReadRequest(Base):
    last_read_message_id: PositiveInt


class Chat(Base):
    id: PositiveInt
    chat_type: tables.ChatType
    title: str | None = None
    created_by_id: PositiveInt


class ChatDetail(Chat):
    members: list[ChatMember]


class SendMessageRequest(Base):
    idempotency_key: uuid.UUID
    text: str = pydantic.Field(min_length=1, max_length=4000)


class EditMessageRequest(Base):
    text: str = pydantic.Field(min_length=1, max_length=4000)


class Message(Base):
    id: PositiveInt
    chat_id: PositiveInt
    user_id: PositiveInt | None = None
    text: str
    created_at: datetime.datetime
    edited_at: datetime.datetime | None = None


class Messages(Collection[Message]):
    pass


class ChatListItem(Chat):
    last_message: Message | None = None
    unread_count: int = 0


class Chats(Collection[ChatListItem]):
    pass
