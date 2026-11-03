---
doc_id: TEST-STRAT-004
title: Sensor Monitoring Test Strategy
version: "1.0"
section: Testing
---

# Sensor Monitoring Test Strategy

## Objectives

Validate that timeout thresholds, heartbeat sequencing, and offline fallback behavior match
REF-ARCH-001 and SPEC-HB-010.

## Test tiers

1. **Unit** — timeout state machine transitions (Healthy → Degraded → Offline → Degraded → Healthy).
2. **Integration** — gateway supervisor against a simulated sensor agent.
3. **Fault injection** — drop heartbeats for 45s and 120s; assert Degraded vs Offline.
4. **Regression** — quiet measurement periods with continuing heartbeats must remain Healthy.

## Acceptance examples

| Scenario | Expected result |
|---|---|
| Heartbeats every 10s | Remains Healthy |
| Gap of 45s then resume | Enters Degraded; returns to Healthy after recovery rule |
| Gap of 120s | Enters Offline; discards measurements older than 5 minutes |
| Measurements stop, heartbeats continue | Remains Healthy |

## Out of scope for this strategy

- Formal verification against IEC/ISO functional-safety standards.
- Hardware watchdog silicon behavior on specific SoCs.
- Performance benchmarking of cloud ingestion under load.
