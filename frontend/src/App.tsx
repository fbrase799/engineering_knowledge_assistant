import { useEffect, useMemo, useState, type FormEvent } from "react";
import { askQuestionStream, fetchCorpus, fetchExamples, fetchGraphMermaid } from "./api";
import GraphDiagram from "./GraphDiagram";
import type {
  AskResponse,
  CorpusCatalog,
  ExampleQuestion,
  ExecutionEvent,
  RetrievalMode,
} from "./types";

const MODES: { id: RetrievalMode; label: string; blurb: string }[] = [
  { id: "hybrid", label: "Hybrid", blurb: "Compare documents + web" },
  { id: "local", label: "Local", blurb: "Engineering knowledge only" },
  { id: "web", label: "Web", blurb: "Tavily search only" },
];

export default function App() {
  const [mode, setMode] = useState<RetrievalMode>("hybrid");
  const [question, setQuestion] = useState("");
  const [examples, setExamples] = useState<ExampleQuestion[]>([]);
  const [corpus, setCorpus] = useState<CorpusCatalog | null>(null);
  const [scenarioOpen, setScenarioOpen] = useState(false);
  const [graphOpen, setGraphOpen] = useState(false);
  const [graphMermaid, setGraphMermaid] = useState<string | null>(null);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [expandedDocId, setExpandedDocId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [liveEvents, setLiveEvents] = useState<ExecutionEvent[]>([]);

  useEffect(() => {
    fetchExamples()
      .then(setExamples)
      .catch(() => setExamples([]));
    fetchCorpus()
      .then(setCorpus)
      .catch(() => setCorpus(null));
  }, []);

  useEffect(() => {
    if (!scenarioOpen && !graphOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setScenarioOpen(false);
        setGraphOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [scenarioOpen, graphOpen]);

  const modeExamples = useMemo(
    () => examples.filter((example) => example.retrieval_mode === mode),
    [examples, mode],
  );

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
    // Mode is already selected; keep examples scoped to the active retrieval mode.
  }

  function clearAnswer() {
    setResult(null);
    setLiveEvents([]);
    setError(null);
  }

  async function openGraph() {
    setGraphOpen(true);
    setGraphError(null);
    if (graphMermaid) return;
    try {
      setGraphMermaid(await fetchGraphMermaid());
    } catch (err) {
      setGraphError(err instanceof Error ? err.message : "Failed to load graph");
    }
  }

  const questionPlaceholder =
    mode === "local"
      ? "What timeout thresholds and fallback states are specified in our architecture?"
      : mode === "web"
        ? "What do current official sources say about watchdog strategies on embedded Linux?"
        : "How does our sensor timeout strategy compare with current watchdog recommendations?";

  return (
    <div className="app-shell">
      <header className="title-bar">
        <h1 className="brand-title">Engineering Knowledge Assistant</h1>
        <p className="tech-stack" aria-label="Technology stack">
          <span className="tech-stack-label">Technology Stack</span>
          <span className="tech-stack-items">
            LangChain <span aria-hidden="true">·</span> LangGraph{" "}
            <span aria-hidden="true">·</span> RAG
          </span>
        </p>
      </header>

      <main className="page">
        <div className="layout">
          <section className="panel">
            <div className="scenario-callout">
              <div>
                <p className="knowledge-caption">Engineering knowledge</p>
                <p className="knowledge-copy">
                  {corpus?.scenario.summary ??
                    "Your engineering knowledge is a read-only set of documents — a synthetic story about edge sensors, heartbeat supervision, and timeout handling. The documents are processed and stored in a local RAG."}
                </p>
              </div>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setScenarioOpen(true)}
                disabled={!corpus}
              >
                View knowledge
              </button>
            </div>

            <form id="ask-form" onSubmit={onSubmit}>
              <p className="section-label">Retrieval mode</p>
              <div className="mode-row" role="radiogroup" aria-label="Retrieval mode">
                {MODES.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    role="radio"
                    aria-checked={mode === item.id}
                    className={mode === item.id ? "option-card selected" : "option-card"}
                    onClick={() => setMode(item.id)}
                  >
                    <span className="option-title">{item.label}</span>
                    <small>{item.blurb}</small>
                  </button>
                ))}
              </div>

              <label className="section-label" htmlFor="question">
                Engineering question
              </label>
              <textarea
                id="question"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder={questionPlaceholder}
                rows={5}
                required
              />

              <div className="prompt-actions">
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={loading || !question.trim()}
                >
                  {loading ? "Running…" : "Ask"}
                </button>
                <p className="hint">
                  Examples below match the selected mode
                  {mode === "hybrid"
                    ? " (documents + web)"
                    : mode === "local"
                      ? " (engineering knowledge only)"
                      : " (public web only)"}
                  .
                </p>
              </div>
            </form>

            {modeExamples.length > 0 && (
              <div className="examples">
                <p className="section-label">
                  Example questions · {mode === "hybrid" ? "Hybrid" : mode === "local" ? "Local" : "Web"}
                </p>
                <div className="example-list">
                  {modeExamples.map((example) => (
                    <button
                      key={`${example.retrieval_mode}-${example.label}`}
                      type="button"
                      className="option-card example"
                      onClick={() => applyExample(example)}
                    >
                      <span className="option-title">{example.label}</span>
                      <small>{example.question}</small>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </section>

          <section
            className={
              result
                ? "panel result-panel result-panel--active"
                : "panel result-panel result-panel--idle"
            }
          >
            {error && <div className="banner error">{error}</div>}
            {!result && !loading && !error && (
              <div className="empty">
                <p>
                  <strong>Hybrid (default)</strong> retrieves from your engineering knowledge and
                  runs one public web search, then synthesizes a source-separated comparison with
                  citations and a live execution timeline.
                </p>
                <p>
                  <strong>Local</strong> answers only from the curated documents — use it to
                  understand what our design already specifies (thresholds, decisions, runbooks).
                </p>
                <p>
                  <strong>Web</strong> searches public sources only — use it to research current
                  external guidance without consulting the local knowledge base.
                </p>
                <p>
                  Open <strong>View knowledge</strong> to inspect the local engineering documents
                  being protected and analyzed.
                </p>
              </div>
            )}

            {result && (
              <div className="answer-toolbar">
                <button type="button" className="btn-secondary" onClick={clearAnswer}>
                  Clear Answer
                </button>
                <button type="button" className="btn-secondary" onClick={() => void openGraph()}>
                  Show Graph
                </button>
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
                    !result.sections.comparison &&
                    (result.answer_markdown ? (
                      <section>
                        <h2>Answer</h2>
                        <pre className="markdown">{result.answer_markdown}</pre>
                      </section>
                    ) : (
                      !result.error && (
                        <div className="banner warn">
                          The model returned no visible answer text. Try again, or raise
                          LLM_MAX_TOKENS for gpt-5-* Azure deployments.
                        </div>
                      )
                    ))}
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
                      LLM {result.usage_metrics.llm_calls} · Tavily{" "}
                      {result.usage_metrics.tavily_calls}
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
        </div>
      </main>

      {graphOpen && (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => setGraphOpen(false)}
        >
          <div
            className="modal modal--graph"
            role="dialog"
            aria-modal="true"
            aria-labelledby="graph-dialog-title"
            onClick={(event) => event.stopPropagation()}
          >
            {graphError && <div className="banner error">{graphError}</div>}
            {!graphError && !graphMermaid && <p className="muted">Loading graph…</p>}
            <div className="graph-layout graph-layout--split">
              <div className="graph-layout-diagram">
                {graphMermaid && <GraphDiagram definition={graphMermaid} />}
              </div>
              <aside className="graph-sidebar">
                <div className="graph-sidebar-header">
                  <div>
                    <p className="section-label">LangGraph</p>
                    <h2 id="graph-dialog-title">Compiled retrieval workflow</h2>
                  </div>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => setGraphOpen(false)}
                  >
                    Close
                  </button>
                </div>
                <p className="hint">
                  Diagram generated from the compiled LangGraph. When you ask a question, the path
                  below shows which nodes ran for that answer.
                </p>
                {liveEvents.length > 0 ? (
                  <div className="graph-path">
                    <p className="section-label">This request path</p>
                    <ol>
                      {liveEvents.map((evt) => (
                        <li key={`graph-${evt.event_id}`}>
                          <strong>{evt.node}</strong>
                          {evt.branch ? ` · ${evt.branch}` : ""} — {evt.status}
                        </li>
                      ))}
                    </ol>
                  </div>
                ) : (
                  <p className="muted">Ask a question to see the executed path for that request.</p>
                )}
              </aside>
            </div>
          </div>
        </div>
      )}

      {scenarioOpen && corpus && (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => setScenarioOpen(false)}
        >
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="corpus-dialog-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <p className="section-label">Engineering knowledge</p>
                <h2 id="corpus-dialog-title">{corpus.scenario.title}</h2>
              </div>
              <button type="button" className="btn-secondary" onClick={() => setScenarioOpen(false)}>
                Close
              </button>
            </div>

            <p>{corpus.scenario.summary}</p>

            <div className="scenario-grid">
              <article className="scenario-card">
                <h3>What we protect</h3>
                <p>{corpus.scenario.what_we_protect}</p>
              </article>
              <article className="scenario-card">
                <h3>What we analyze</h3>
                <p>{corpus.scenario.what_we_analyze}</p>
              </article>
            </div>

            <p className="muted index-meta">
              Knowledge index: {corpus.index.document_count ?? corpus.documents.length} documents
              {corpus.index.chunk_count != null ? ` · ${corpus.index.chunk_count} chunks` : ""}
              {corpus.index.embedding_model ? ` · ${corpus.index.embedding_model}` : ""}
            </p>

            <div className="corpus-docs">
              {corpus.documents.map((doc) => {
                const open = expandedDocId === doc.doc_id;
                return (
                  <details
                    key={doc.doc_id}
                    className="corpus-doc"
                    open={open}
                    onToggle={(event) => {
                      const el = event.currentTarget;
                      setExpandedDocId(el.open ? doc.doc_id : null);
                    }}
                  >
                    <summary>
                      <span className="option-title">{doc.title}</span>
                      <span className="muted">
                        {doc.doc_id} · v{doc.version} · {doc.section}
                      </span>
                      <span className="doc-summary">{doc.summary}</span>
                    </summary>
                    <pre className="doc-body">{doc.content_markdown}</pre>
                  </details>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
