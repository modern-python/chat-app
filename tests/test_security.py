from app.security import hash_password, verify_password


def test_hash_is_not_the_plaintext() -> None:
    hashed = hash_password("hunter2")
    assert hashed != "hunter2"
    assert hashed.startswith("$argon2")


def test_verify_accepts_correct_password() -> None:
    assert verify_password(hash_password("hunter2"), "hunter2") is True


def test_verify_rejects_wrong_password() -> None:
    assert verify_password(hash_password("hunter2"), "hunter3") is False


def test_verify_rejects_malformed_hash() -> None:
    assert verify_password("not-a-hash", "hunter2") is False
