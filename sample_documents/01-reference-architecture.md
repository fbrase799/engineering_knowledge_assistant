---
doc_id: REF-ARCH-001
title: Sensor Monitoring Reference Architecture
version: "1.2"
section: Overview
---

# Sensor Monitoring Reference Architecture

## Document purpose

This reference architecture describes a synthetic **fleet sensor monitoring** system used
to illustrate timeout handling, heartbeat supervision, and failure detection for edge devices.

## System context

Edge sensors publish telemetry to a local gateway. The gateway forwards batches to a cloud
ingestion service. Operators require timely detection when a sensor stops reporting, without
false alarms during brief network interruptions.

## Logical components

1. **Sensor Agent** — runs on the edge device; emits measurements and a heartbeat.
2. **Gateway Supervisor** — tracks last-seen timestamps and applies timeout policy.
3. **Cloud Ingestion API** — receives batches; does not perform primary liveness decisions.
4. **Operator Console** — displays device health derived from gateway supervisor state.

## Timeout strategy (documented design)

The gateway supervisor classifies devices using a **two-tier timeout**:

| State | Condition | Operator meaning |
|---|---|---|
| Healthy | Heartbeat received within **30 seconds** | Device reporting normally |
| Degraded | No heartbeat for **30–90 seconds** | Investigate connectivity; still expect recovery |
| Offline | No heartbeat for **more than 90 seconds** | Declare device offline; raise alert |

Fallback behavior when Offline:

- Stop accepting stale queued measurements older than 5 minutes.
- Mark the device `OFFLINE` in the operator console.
- Require a successful heartbeat before returning to Healthy (no automatic jump from Offline to Healthy without an intervening Degraded observation window of at least one successful heartbeat cycle).

## Non-goals

This architecture does not claim compliance with any specific functional-safety standard.
It is a synthetic design baseline for comparison with external watchdog guidance.
