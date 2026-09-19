# Sequence ids, not snowflakes

`messages.id` is a plain BigInt identity column, so Postgres assigns values
monotonically and supplies the total ordering that cursor pagination
(`before_id`), catch-up (`after_id`) and client-side gap detection all read off
the primary key index. Snowflake ids, the usual choice for a chat backend, were
rejected: what they buy is coordination-free generation across independent
writers, and this service has exactly one writer, Postgres, so there is no
coordination problem to solve and an id-generation component plus a machine-id
assignment concern would be added to demonstrate nothing. Time-based ids would
also be strictly worse for gap detection, because clock skew makes "is my next
id contiguous with the last one I saw" unanswerable where a sequence makes it a
comparison. Message writes that reach storage without passing through Postgres,
or a partitioned `messages` table, would reopen this.
