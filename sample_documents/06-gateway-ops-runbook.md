---
doc_id: RUN-GW-006
title: Gateway Supervisor Operations Runbook
version: "1.0"
section: Runbook
---

# Gateway Supervisor Operations Runbook

## Scope

Operational steps for diagnosing heartbeat gaps and recovering Offline devices in the synthetic
fleet sensor monitoring design.

## Symptoms and first checks

1. **Many devices Degraded simultaneously** — inspect gateway NTP sync, upstream network path,
   and batch-forwarder backlog before blaming individual sensors.
2. **Single device Offline** — verify agent process, local power, and that heartbeat interval is
   still configured to **10 seconds**.
3. **Healthy heartbeats but missing measurements** — treat as Healthy per ADR-WATCHDOG-003;
   investigate sensor quiet-period configuration separately.

## Recovery procedure after Offline

1. Confirm at least one valid heartbeat arrived at the gateway.
2. Expect Degraded for one heartbeat interval before Healthy (anti-flap rule in SPEC-HB-010).
3. Re-enable acceptance of fresh measurements; do not replay packets older than **5 minutes**.
4. Clear `UNSTABLE` only after a human acknowledgement in the operator console.

## Maintenance windows

During planned maintenance, operators may place a device in `MAINTENANCE`, which:

- Suppresses Offline paging
- Continues recording heartbeats for diagnostics
- Automatically exits `MAINTENANCE` after the configured window (default **2 hours**) unless renewed

## Logging retention

Gateway supervisor retains last-seen timestamps and state transitions for **30 days** for
post-incident review. Raw heartbeat payloads are retained for **7 days**.
