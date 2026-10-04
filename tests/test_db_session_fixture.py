import pytest


pytest_plugins = ["pytester"]


def test_db_session_teardown_fails_when_outer_transaction_was_committed(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import sqlalchemy as sa
        from sqlalchemy.ext.asyncio import AsyncSession

        from tests.conftest import app, db_session, di_container

        captured = {}


        async def test_commits_outer_transaction(db_session):
            captured["connection"] = db_session.bind
            session = AsyncSession(db_session.bind, join_transaction_mode="control_fully")
            await session.execute(sa.text("SELECT 1"))
            await session.commit()
            await session.close()


        def test_connection_was_still_closed():
            assert captured["connection"].closed
        """,
    )

    result = pytester.runpytest_inprocess(
        "-p",
        "no:cacheprovider",
        "-o",
        "asyncio_mode=auto",
        "-o",
        "asyncio_default_fixture_loop_scope=function",
        "-W",
        "error",
    )

    result.assert_outcomes(passed=2, errors=1)
    result.stdout.fnmatch_lines(["*outer test transaction is no longer active*create_savepoint*"])
