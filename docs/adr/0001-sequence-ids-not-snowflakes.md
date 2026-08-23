# Sequence ids, not snowflakes

`messages.id` is a plain BigInt identity column. Postgres assigns values
monotonically, which supplies the total ordering that cursor pagination
(`before_id`), catch-up (`after_id`), and client-side gap detection all read off
the primary key index.

## Rejected: snowflake ids

64-bit time-sortable ids assembled from timestamp, machine id, and sequence.
Their advantage is coordination-free generation across independent writers while
staying k-sortable. This service has one writer, Postgres, so the coordination
problem it solves does not exist here. Adopting them would add an id-generation
component and a machine-id assignment concern to demonstrate nothing the repo is
about.

Time-based ids would also be strictly worse for gap detection: clock skew makes
"is my next id contiguous with the last one I saw" unanswerable, whereas a
sequence makes it a comparison.

## Revisit trigger

Message writes originating from more than one process without passing through
Postgres, or a partitioned/sharded messages table.
