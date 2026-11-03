"""API-level tests."""

from __future__ import annotations

import json

from backend.src.retrieval.models import RetrievalMode


def test_health(client):
    test_client, _ = client
    response = test_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_ask_defaults_to_hybrid(client):
    test_client, _ = client
    response = test_client.post(
        "/api/ask",
        json={"question": "How do our timeouts compare with public watchdog guidance?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["retrieval_mode"] == RetrievalMode.HYBRID.value
    assert body["comparison_status"] == "full"
    assert body["sections"]["comparison"]
    assert body["execution_events"]


def test_examples_endpoint(client):
    test_client, _ = client
    response = test_client.get("/api/examples")
    assert response.status_code == 200
    examples = response.json()["examples"]
    assert any(ex["retrieval_mode"] == "hybrid" for ex in examples)


def test_ask_stream_emits_events(client):
    test_client, _ = client
    with test_client.stream(
        "POST",
        "/api/ask/stream",
        json={
            "question": "Compare heartbeat design with public guidance",
            "retrieval_mode": "hybrid",
        },
    ) as response:
        assert response.status_code == 200
        payloads = []
        for line in response.iter_lines():
            if line.startswith("data:"):
                payloads.append(line.removeprefix("data:").strip())
        assert payloads
        # Final payload should be the full result JSON
        last = json.loads(payloads[-1])
        assert last["request_id"]
        assert last["answer_markdown"]
