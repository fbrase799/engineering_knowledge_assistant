import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 2.5;
const ZOOM_STEP = 0.25;
const DEFAULT_ZOOM = 1;

/** LangGraph emits HTML wrappers like [<p>label</p>]; strip for strict Mermaid. */
function sanitizeMermaid(definition: string): string {
  return definition
    .replace(/<\/?p>/gi, "")
    .replace(/&lt;\/?p&gt;/gi, "")
    .trim();
}

type Props = {
  definition: string;
};

export default function GraphDiagram({ definition }: Props) {
  const reactId = useId().replace(/:/g, "");
  const stageRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(DEFAULT_ZOOM);
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    setSvg(null);
    setError(null);
    setNaturalSize(null);

    async function render() {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "neutral",
          flowchart: { curve: "linear", htmlLabels: false },
        });
        const { svg: rendered } = await mermaid.render(
          `langgraph-${reactId}`,
          sanitizeMermaid(definition),
        );
        if (!cancelled) setSvg(rendered);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to render diagram");
        }
      }
    }

    void render();
    return () => {
      cancelled = true;
    };
  }, [definition, reactId]);

  useLayoutEffect(() => {
    if (!svg || !stageRef.current) return;
    const svgEl = stageRef.current.querySelector("svg");
    if (!svgEl) return;

    const widthAttr = Number(svgEl.getAttribute("width"));
    const heightAttr = Number(svgEl.getAttribute("height"));
    const viewBox = svgEl.viewBox?.baseVal;
    const w =
      (Number.isFinite(widthAttr) && widthAttr > 0 && widthAttr) ||
      viewBox?.width ||
      svgEl.getBoundingClientRect().width ||
      480;
    const h =
      (Number.isFinite(heightAttr) && heightAttr > 0 && heightAttr) ||
      viewBox?.height ||
      svgEl.getBoundingClientRect().height ||
      640;

    setNaturalSize({ w, h });
    svgEl.removeAttribute("width");
    svgEl.removeAttribute("height");
    svgEl.style.width = `${w}px`;
    svgEl.style.height = `${h}px`;
    svgEl.style.maxWidth = "none";
  }, [svg]);

  function adjustZoom(delta: number) {
    setZoom((current) =>
      Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Math.round((current + delta) * 100) / 100)),
    );
  }

  if (error) {
    return (
      <div className="graph-diagram graph-diagram--fallback">
        <p className="muted">Could not render diagram: {error}</p>
        <pre className="graph-mermaid">{definition}</pre>
      </div>
    );
  }

  if (!svg) {
    return <p className="muted">Rendering diagram…</p>;
  }

  const stageWidth = naturalSize ? naturalSize.w * zoom : undefined;
  const stageHeight = naturalSize ? naturalSize.h * zoom : undefined;

  return (
    <div className="graph-diagram">
      <div className="graph-diagram-toolbar">
        <span className="graph-diagram-zoom-label">{Math.round(zoom * 100)}%</span>
        <button
          type="button"
          className="btn-secondary graph-zoom-btn"
          aria-label="Zoom out"
          disabled={zoom <= MIN_ZOOM}
          onClick={() => adjustZoom(-ZOOM_STEP)}
        >
          −
        </button>
        <button
          type="button"
          className="btn-secondary graph-zoom-btn"
          aria-label="Zoom in"
          disabled={zoom >= MAX_ZOOM}
          onClick={() => adjustZoom(ZOOM_STEP)}
        >
          +
        </button>
        <button
          type="button"
          className="btn-secondary graph-zoom-btn graph-zoom-reset"
          aria-label="Reset zoom"
          onClick={() => setZoom(DEFAULT_ZOOM)}
        >
          Reset
        </button>
      </div>
      <div className="graph-diagram-viewport">
        <div
          className="graph-diagram-scaler"
          style={{
            width: stageWidth,
            height: stageHeight,
          }}
        >
          <div
            ref={stageRef}
            className="graph-diagram-stage"
            style={{ transform: `scale(${zoom})` }}
            role="img"
            aria-label="Compiled LangGraph retrieval workflow"
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        </div>
      </div>
    </div>
  );
}
