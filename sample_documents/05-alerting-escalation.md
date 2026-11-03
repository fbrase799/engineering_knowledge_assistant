---
doc_id: ALERT-ESC-005
title: Alerting and Escalation Policy
version: "1.0"
section: Operations
---

# Alerting and Escalation Policy

## Purpose

Define how the gateway supervisor notifies operators when devices enter Degraded or Offline
states in the synthetic sensor monitoring system.

## Alert triggers

| State transition | Severity | Channel | Delay before notify |
|---|---|---|---|
| Healthy → Degraded | Warning | Operator console + email digest | Immediate console; email after 2 minutes if still Degraded |
| Degraded → Offline | Critical | Console + paging webhook | Immediate |
| Offline → Degraded (recovery) | Info | Console only | Immediate |
| Degraded → Healthy | Info | Console only | Immediate |

## Flapping suppression

- Do not page more than once per device per **15 minutes** for repeated Offline transitions.
- Console events are always recorded; paging is rate-limited.
- A device that oscillates between Degraded and Offline three times within 30 minutes is marked
  `UNSTABLE` and requires manual acknowledgement before returning to normal paging rules.

## Escalation

1. On-call engineer receives critical pages.
2. If unacknowledged for **20 minutes**, escalate to the fleet reliability lead.
3. Customer-facing status notes are out of scope for this synthetic document.

## Explicit non-claims

This policy does not define SLA credits, regulatory notification duties, or safety-case evidence.
