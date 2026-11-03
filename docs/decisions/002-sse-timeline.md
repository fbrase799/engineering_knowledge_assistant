# ADR-002: SSE for execution timeline

## Status

Accepted

## Context

The PRD allows SSE or post-hoc fetch for the first milestone. A live timeline better showcases LangGraph node execution.

## Decision

Expose `POST /api/ask/stream` (SSE) that emits `started`, `node`, `result`, and `error` events. Keep `POST /api/ask` for simple clients and tests.

## Consequences

- Frontend can render progressive trace items
- Slightly more complex API surface
- Nginx must disable proxy buffering for SSE (configured in `docker/nginx.conf`)
