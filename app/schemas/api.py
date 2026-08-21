from typing import Self

import pydantic
from pydantic import BaseModel, PositiveInt


class Base(BaseModel):
    model_config = pydantic.ConfigDict(from_attributes=True)


class Collection[T: Base](Base):
    items: list[T]

    @classmethod
    def from_models(cls, objects: object) -> Self:
        return cls.model_validate({"items": list(objects)})  # ty: ignore[invalid-argument-type]


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
