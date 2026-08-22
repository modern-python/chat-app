---
summary: `unsubscribe` removes the subscriber but leaves the now-empty channel entry behind in `self._channels`, growing unboundedly with distinct users.
---

# Litestar channels: empty channel entries retained after unsubscribe

## Why it is open

`unsubscribe` removes the subscriber but leaves the now-empty `set()` and its key
in `self._channels`. With per-user channel names that dict grows by one entry per
distinct user that ever connects, in a singleton that lives for the whole
process. Upstream:
[litestar#4867](https://github.com/litestar-org/litestar/issues/4867).

`rchat`'s `PruningChannelsPlugin` overrides the public `unsubscribe` to drop
empty entries, so this one needs no private access. Still not shipped, for
symmetry with the item above and because the growth is bounded by distinct users
in a demo.

## Revisit trigger

Upstream fix released, or the app being run anywhere with a non-trivial user
population.
