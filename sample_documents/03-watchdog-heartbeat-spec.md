---
doc_id: SPEC-HB-010
title: Watchdog and Heartbeat Specification
version: "1.1"
section: Specification
---

# Watchdog and Heartbeat Specification

## Scope

This specification defines heartbeat content, timing, and gateway reaction for the synthetic
sensor monitoring system.

## Heartbeat message

| Field | Type | Description |
|---|---|---|
| `device_id` | string | Stable device identifier |
| `seq` | uint64 | Monotonic sequence number |
| `sent_at` | ISO-8601 UTC | Agent send timestamp |
| `agent_version` | string | SemVer of the sensor agent |

## Timing parameters

| Parameter | Value | Notes |
|---|---|---|
| Heartbeat interval | 10 s | Agent target cadence |
| Degraded threshold | 30 s | Enter Degraded |
| Offline threshold | 90 s | Enter Offline |
| Stale measurement discard | 5 min | Applied after Offline |

## Failure detection rules

1. Missing heartbeats drive state transitions; measurement gaps do not.
2. Out-of-order heartbeats with older `seq` are ignored.
3. Clock skew up to 5 seconds is tolerated using gateway receive time as the primary clock
   for timeout evaluation; `sent_at` is retained for diagnostics only.
4. After Offline, the first valid heartbeat moves the device to Degraded for one full
   heartbeat interval before Healthy, reducing flapping.

## Explicit limitations

- No automatic remote reboot is performed by the gateway.
- No claim is made that these thresholds are optimal for all embedded Linux deployments.
- External watchdog best practices may recommend different recovery actions; those are
  candidates for comparison, not automatic overrides of this specification.
