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
  });
});
