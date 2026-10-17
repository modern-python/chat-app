# Pool pre-ping is off and postgres_retry recovers dead connections

`pool_pre_ping` defaults to off. A pooled connection that died while idle fails
its first statement, SQLAlchemy marks the error `connection_invalidated`, and
`postgres_retry` runs the use case again on a fresh connection. Pre-ping was
rejected because it adds a BEGIN, a ping and a ROLLBACK to every checkout, and a
request makes two checkouts. Measured on `GET /api/auth/me/` and the message
list, it cost 7 to 35% of throughput on a local network and 40 to 57% with 1 ms
of database latency. The retry needs one rule: every query a retried use case
runs goes inside its `Transaction` block. Entering `Transaction` rolls back a
session whose connection was lost, so a query after the block is recovered, but
a query before it still fails the retry.
`tests/use_cases/test_connection_loss.py` kills a connection both while it is
idle in the pool and while a session holds it.
