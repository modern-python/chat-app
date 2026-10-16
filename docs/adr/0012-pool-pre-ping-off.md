# Pool pre-ping is off and postgres_retry recovers dead connections

`pool_pre_ping` defaults to off. A pooled connection that died while idle fails
its first statement, SQLAlchemy marks the error `connection_invalidated`, and
`postgres_retry` runs the use case again on a fresh connection. Pre-ping was
rejected because it adds a BEGIN, a ping and a ROLLBACK to every checkout, and a
request makes two checkouts. Measured on `GET /api/auth/me/` and the message
list, it cost 7 to 35% of throughput on a local network and 40 to 57% with 1 ms
of database latency. The price of the retry is a rule the code must keep: every
query a retried use case runs goes inside its `Transaction` block, because a
query outside it leaves the session in a dead transaction that the retry cannot
roll back. `tests/use_cases/test_connection_loss.py` kills a connection both
while it is idle in the pool and while a session holds it.
