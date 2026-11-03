import { useEffect, useMemo, useState, type FormEvent } from "react";
import { askQuestionStream, fetchExamples } from "./api";
import type { AskResponse, ExampleQuestion, ExecutionEvent, RetrievalMode } from "./types";

const MODES: { id: RetrievalMode; label: string; blurb: string }[] = [
  { id: "hybrid", label: "Hybrid", blurb: "Compare documents + web" },
  { id: "local", label: "Local", blurb: "Curated corpus only" },
  { id: "web", label: "Web", blurb: "Tavily search only" },
];

export default function App() {
  const [mode, setMode] = useState<RetrievalMode>("hybrid");
  const [question, setQuestion] = useState("");
  const [examples, setExamples] = useState<ExampleQuestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [liveEvents, setLiveEvents] = useState<ExecutionEvent[]>([]);

  useEffect(() => {
    fetchExamples()
      .then(setExamples)
      .catch(() => setExamples([]));
  }, []);

  const docCitations = useMemo(
    () => result?.citations.filter((c) => c.source_type === "document") ?? [],
    [result],
  );
  const webCitations = useMemo(
    () => result?.citations.filter((c) => c.source_type === "web") ?? [],
    [result],
  );

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setLiveEvents([]);
    try {
      const response = await askQuestionStream(question.trim(), mode, (evt) => {
        setLiveEvents((prev) => [...prev, evt]);
      });
      setResult(response);
      setLiveEvents(response.execution_events);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  function applyExample(example: ExampleQuestion) {
    setQuestion(example.question);
    setMode(example.retrieval_mode);
  }

  return (
    <div className="page">
      <div className="atmosphere" aria-hidden="true" />
      <header className="hero">
        <p className="brand">Engineering Knowledge Assistant</p>
        <h1>Compare curated design docs with current public guidance.</h1>
        <p className="lede">
          One shared RAG corpus, one targeted web search, one synthesis call — with an
          inspectable LangGraph execution path.
        </p>
      </header>

      <main className="layout">
        <section className="ask-panel">
          <form onSubmit={onSubmit}>
            <div className="mode-row" role="radiogroup" aria-label="Retrieval mode">
              {MODES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="radio"
                  aria-checked={mode === item.id}
                  className={mode === item.id ? "mode active" : "mode"}
                  onClick={() => setMode(item.id)}
                >
                  <span>{item.label}</span>
                  <small>{item.blurb}</small>
                </button>
              ))}
            </div>

            <label className="field-label" htmlFor="question">
              Engineering question
            </label>
            <textarea
              id="question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="How does our sensor timeout strategy compare with current watchdog recommendations?"
              rows={5}
              required
            />

            <div className="actions">
              <button type="submit" className="primary" disabled={loading}>
                {loading ? "Running graph…" : "Ask"}
              </button>
              <span className="doc-link">See repo docs/ for architecture, LangGraph, and RAG flow</span>
            </div>
          </form>

          {examples.length > 0 && (
            <div className="examples">
              <p className="field-label">Example questions</p>
              <div className="example-list">
                {examples.map((example) => (
                  <button
                    key={example.label}
                    type="button"
                    className="example"
                    onClick={() => applyExample(example)}
                  >
                    <strong>{example.label}</strong>
                    <span>{example.question}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>

        <section className="result-panel">
          {error && <div className="banner error">{error}</div>}
          {!result && !loading && !error && (
            <div className="empty">
              Choose Hybrid (default) to see a source-separated comparison with citations and a live
              execution timeline.
            </div>
          )}

          {(loading || liveEvents.length > 0) && (
            <details className="trace" open>
              <summary>Execution trace</summary>
              <ol>
                {liveEvents.map((evt) => (
                  <li key={evt.event_id} className={`trace-item ${evt.status}`}>
                    <div>
                      <strong>{evt.node}</strong>
                      {evt.branch ? <em> · {evt.branch}</em> : null}
                    </div>
                    <p>{evt.message}</p>
                    <span>
                      {evt.status}
                      {evt.duration_ms != null ? ` · ${evt.duration_ms.toFixed(1)} ms` : ""}
                    </span>
                  </li>
                ))}
              </ol>
            </details>
          )}

          {result && (
            <>
              {result.sections.evidence_gap_message && (
                <div className="banner warn">{result.sections.evidence_gap_message}</div>
              )}

              <article className="answer">
                {result.sections.documented_approach && (
                  <section>
                    <h2>Documented approach</h2>
                    <p>{result.sections.documented_approach}</p>
                  </section>
                )}
                {result.sections.web_findings && (
                  <section>
                    <h2>Current web findings</h2>
                    <p>{result.sections.web_findings}</p>
                  </section>
                )}
                {result.sections.comparison && (
                  <section>
                    <h2>Comparison</h2>
                    <p>{result.sections.comparison}</p>
                  </section>
                )}
                {result.sections.engineering_implications && (
                  <section>
                    <h2>Engineering implications</h2>
                    <p className="proposal">{result.sections.engineering_implications}</p>
                  </section>
                )}
                {!result.sections.documented_approach &&
                  !result.sections.web_findings &&
                  !result.sections.comparison && (
                    <section>
                      <h2>Answer</h2>
                      <pre className="markdown">{result.answer_markdown}</pre>
                    </section>
                  )}
              </article>

              <div className="sources">
                <section>
                  <h3>Document sources</h3>
                  {docCitations.length === 0 ? (
                    <p className="muted">None</p>
                  ) : (
                    <ul>
                      {docCitations.map((c) => (
                        <li key={c.source_id}>
                          <strong>{c.label}</strong>
                          <span>{c.reference}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
                <section>
                  <h3>Web sources</h3>
                  {webCitations.length === 0 ? (
                    <p className="muted">None</p>
                  ) : (
                    <ul>
                      {webCitations.map((c) => (
                        <li key={c.source_id}>
                          <a href={c.reference} target="_blank" rel="noreferrer">
                            {c.label}
                          </a>
                          <span>
                            Retrieved{" "}
                            {String(c.metadata.retrieved_at ?? "during this request")}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </div>

              <dl className="summary">
                <div>
                  <dt>Request</dt>
                  <dd>{result.request_id}</dd>
                </div>
                <div>
                  <dt>Duration</dt>
                  <dd>{result.duration_ms.toFixed(0)} ms</dd>
                </div>
                <div>
                  <dt>Local / Web</dt>
                  <dd>
                    {result.usage_metrics.local_chunk_count} chunks /{" "}
                    {result.usage_metrics.web_result_count} results
                  </dd>
                </div>
                <div>
                  <dt>Calls</dt>
                  <dd>
                    LLM {result.usage_metrics.llm_calls} · Tavily {result.usage_metrics.tavily_calls}
                  </dd>
                </div>
                <div>
                  <dt>Tokens</dt>
                  <dd>
                    {result.usage_metrics.total_tokens ?? "unavailable"}
                    {result.usage_metrics.estimated_cost_usd != null
                      ? ` · ~$${result.usage_metrics.estimated_cost_usd.toFixed(5)} (${result.usage_metrics.cost_status})`
                      : ` · cost ${result.usage_metrics.cost_status}`}
                  </dd>
                </div>
              </dl>
            </>
          )}
        </section>
      </main>
    </div>
  );
}
