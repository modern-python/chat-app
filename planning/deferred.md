# Deferred

Real-but-unscheduled items. Each carries a revisit trigger.

## Litestar channels: subscriber orphaned on mid-subscribe disconnect

`ChannelsPlugin.subscribe()` registers the subscriber into `_channels` before
awaiting the history fetch, so a client disconnecting mid-subscribe leaves a
registered subscriber that is never unsubscribed. Upstream:
[litestar#4871](https://github.com/litestar-org/litestar/issues/4871).

`rchat` works around it by reordering the operations, which requires reaching
into `plugin._subscriber_class`, `plugin._channels`, and `plugin._backend`. Not
shipped here: a reference repository demonstrating private-attribute access
teaches the wrong lesson, and the leak is inert at demo scale.

**Revisit trigger:** upstream fix released, or a deployment where connection
churn is high enough for the leak to matter.

## Litestar channels: empty channel entries retained after unsubscribe

`unsubscribe` removes the subscriber but leaves the now-empty `set()` and its key
in `self._channels`. With per-user channel names that dict grows by one entry per
distinct user that ever connects, in a singleton that lives for the whole
process. Upstream:
[litestar#4867](https://github.com/litestar-org/litestar/issues/4867).

`rchat`'s `PruningChannelsPlugin` overrides the public `unsubscribe` to drop
empty entries, so this one needs no private access. Still not shipped, for
symmetry with the item above and because the growth is bounded by distinct users
in a demo.

**Revisit trigger:** upstream fix released, or the app being run anywhere with a
non-trivial user population.

## Presence beyond a TTL key

Presence is planned as a Redis key with a TTL refreshed by the SSE heartbeat.
This reports "has an open stream", not "is looking at this chat", and a client
killed between heartbeats stays online until expiry.

**Revisit trigger:** the demo needing per-chat presence or accurate last-seen.
