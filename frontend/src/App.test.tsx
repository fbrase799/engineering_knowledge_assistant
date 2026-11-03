import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import App from "./App";

describe("App", () => {
  it("defaults to Hybrid mode", () => {
    const html = renderToStaticMarkup(createElement(App));
    expect(html).toContain('aria-checked="true"');
    expect(html).toContain("Hybrid");
    expect(html).toContain("Engineering Knowledge Assistant");
    expect(html).toContain("Technology Stack");
    expect(html).toContain("LangChain");
    expect(html).toContain("LangGraph");
    expect(html).toContain("RAG");
    expect(html).toContain("Examples below match the selected mode (documents + web).");
    expect(html).toContain("Hybrid (default)");
    expect(html).toContain("Local");
    expect(html).toContain("Web");
    expect(html).toContain("View knowledge");
  });
});
