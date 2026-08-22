---
summary: Event fan-out uses one Redis channel per user; per-chat and hybrid topologies rejected.
---

# Per-user channel topology

Every connected client subscribes to exactly one channel, `user:{user_id}`. A
use case resolves the recipient set inside its transaction and carries it in the
event payload; the relay publishes the event once per recipient channel.

## Rejected: per-chat channels

`chat:{chat_id}`, one publish per event regardless of member count. Rejected
because the client must track and resubscribe to N channels as membership
changes, and lifecycle events ("you were added to a chat") have no channel to
arrive on until the client already knows about the chat. Solving that requires a
per-user control channel, so the design ends up with both topologies and the
simplicity of neither.

## Rejected: hybrid

`user:{id}` for chat lifecycle and unread counts, `chat:{id}` for message
traffic. This is the correct choice at scale, because it bounds publish
amplification where the volume is. Rejected for a reference application: the
subscription lifecycle grows a resubscribe path in both the service and the
client, and that machinery obscures the outbox and DI patterns the repo exists
to show.

## Consequence

Publish amplification is O(members) per message. Irrelevant at demo scale,
material in production.

## Revisit trigger

A group chat exceeding ~100 members, or a measured relay bottleneck in the
fan-out loop.
