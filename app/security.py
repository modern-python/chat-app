import typing

import argon2
from argon2.exceptions import Argon2Error


_HASHER: typing.Final = argon2.PasswordHasher()


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _HASHER.verify(password_hash, password)
    except Argon2Error, argon2.exceptions.InvalidHashError:
        return False
