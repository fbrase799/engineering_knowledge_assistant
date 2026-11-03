import type { AskResponse, ExampleQuestion, ExecutionEvent, RetrievalMode } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function fetchExamples(): Promise<ExampleQuestion[]> {
  const res = await fetch(`${API_BASE}/api/examples`);
  if (!res.ok) throw new Error("Failed to load examples");
  const data = await res.json();
  return data.examples;
}

export async function askQuestion(
  question: string,
  retrievalMode: RetrievalMode,
): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/api/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, retrieval_mode: retrievalMode }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export async function askQuestionStream(
  question: string,
  retrievalMode: RetrievalMode,
  onEvent: (event: ExecutionEvent) => void,
): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/api/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, retrieval_mode: retrievalMode }),
  });
  if (!res.ok || !res.body) {
    throw new Error(`Stream failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: AskResponse | null = null;
  let currentEvent = "message";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n");
    buffer = chunks.pop() ?? "";
    for (const raw of chunks) {
      const line = raw.trimEnd();
      if (line.startsWith("event:")) {
        currentEvent = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        const data = line.slice(5).trim();
        if (!data) continue;
        if (currentEvent === "node") {
          onEvent(JSON.parse(data) as ExecutionEvent);
        } else if (currentEvent === "result") {
          result = JSON.parse(data) as AskResponse;
        } else if (currentEvent === "error") {
          const payload = JSON.parse(data) as { error: string };
          throw new Error(payload.error);
        }
      }
    }
  }

  if (!result) throw new Error("Stream ended without a result");
  return result;
}
