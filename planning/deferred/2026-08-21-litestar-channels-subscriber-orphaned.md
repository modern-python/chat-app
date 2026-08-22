---
summary: `ChannelsPlugin.subscribe()` registers a subscriber before awaiting the history fetch, so a client disconnecting mid-subscribe leaves it orphaned and never unsubscribed.
---

# Litestar channels: subscriber orphaned on mid-subscribe disconnect

## Why it is open

`ChannelsPlugin.subscribe()` registers the subscriber into `_channels` before
awaiting the history fetch, so a client disconnecting mid-subscribe leaves a
registered subscriber that is never unsubscribed. Upstream:
[litestar#4871](https://github.com/litestar-org/litestar/issues/4871).

`rchat` works around it by reordering the operations, which requires reaching
into `plugin._subscriber_class`, `plugin._channels`, and `plugin._backend`. Not
shipped here: a reference repository demonstrating private-attribute access
teaches the wrong lesson, and the leak is inert at demo scale.

## Revisit trigger

Upstream fix released, or a deployment where connection churn is high enough
for the leak to matter.
