---
name: DhanHQ v2 wire contract
description: DhanHQ v2 market subscriptions are JSON while ticker responses are fixed binary packets.
---

DhanHQ v2 market-data subscriptions use JSON requests with `RequestCode`,
`InstrumentCount`, and `InstrumentList`; ticker responses use an 8-byte
little-endian header followed by float32 LTP and epoch trade time. Do not infer
the subscription format from the binary response format.

**Why:** An initial implementation guessed a binary subscription packet and
needed correction after checking the current official documentation.

**How to apply:** Verify the official DhanHQ v2 feed and order docs before
changing the adapter or enabling live execution.