---
doc_id: ADR-WATCHDOG-003
title: Design Decision Record — Heartbeat Monitor
version: "1.0"
section: Decisions
---

# ADR-003: Heartbeat Monitor as Primary Liveness Signal

## Status

Accepted (synthetic portfolio document)

## Context

We need a reliable way to detect stalled sensor agents. Options considered:

1. Rely only on measurement message cadence.
2. Use a dedicated heartbeat channel with fixed interval.
3. Use an OS-level hardware watchdog only.

## Decision

Adopt a **dedicated heartbeat monitor** at the gateway:

- Sensor agents emit a heartbeat every **10 seconds**.
- Gateway expects heartbeats with the two-tier timeout (30s / 90s) defined in REF-ARCH-001.
- Measurement messages alone are **not** treated as proof of liveness, because sensors may
  suppress measurements during quiet periods while remaining healthy.

## Consequences

- Operators get consistent liveness semantics independent of telemetry volume.
- Additional network traffic is small (heartbeat payload ≤ 64 bytes).
- A silent measurement stream with continuing heartbeats is treated as Healthy.
- Hardware watchdog reset policy remains a **device-local concern** and is out of scope for
  the gateway supervisor in v1 of this design.

## Alternatives rejected

- Measurement-only liveness: rejected due to quiet-period false offline alerts.
- Hardware-watchdog-only: rejected for fleet visibility; resets are local and not operator-visible.
