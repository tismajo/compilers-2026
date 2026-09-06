/** Unit tests of the compiler contract. Run with `npm test`. */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  buildArgs,
  describeFailure,
  describeSpawnFailure,
  parsePayload,
  resolveSetting,
  summarize,
  toZeroBased,
} from "../protocol";
import { escapeHtml, renderSymbols } from "../render";

describe("resolveSetting", () => {
  it("expands the workspace placeholder", () => {
    const resolved = resolveSetting("${workspaceFolder}/program/Driver.py", "/home/ana/proyecto");
    assert.equal(resolved, "/home/ana/proyecto/program/Driver.py");
  });

  it("keeps spaces in the path", () => {
    const resolved = resolveSetting("${workspaceFolder}/program/Driver.py", "C:\\Mis Proyectos");
    assert.equal(resolved, "C:\\Mis Proyectos/program/Driver.py");
  });
});

describe("buildArgs", () => {
  it("asks for JSON by default", () => {
    const args = buildArgs({ compilerPath: "Driver.py", sourcePath: "a.cps" });
    assert.deepEqual(args, ["Driver.py", "a.cps", "--format", "json"]);
  });

  it("keeps every path as a separate argument", () => {
    const args = buildArgs({
      compilerPath: "C:\\Mis Proyectos\\Driver.py",
      sourcePath: "C:\\Mis Proyectos\\mi programa.cps",
    });
    assert.equal(args[0], "C:\\Mis Proyectos\\Driver.py");
    assert.equal(args[1], "C:\\Mis Proyectos\\mi programa.cps");
  });

  it("adds the tree and symbol flags", () => {
    const args = buildArgs({
      compilerPath: "Driver.py",
      sourcePath: "a.cps",
      tree: "html",
      symbols: "json",
    });
    assert.ok(args.includes("--tree"));
    assert.ok(args.includes("html"));
    assert.ok(args.includes("--symbols"));
    assert.ok(args.includes("json"));
  });

  it("omits the flags when they are 'none'", () => {
    const args = buildArgs({
      compilerPath: "Driver.py",
      sourcePath: "a.cps",
      tree: "none",
      symbols: "none",
    });
    assert.equal(args.includes("--tree"), false);
    assert.equal(args.includes("--symbols"), false);
  });
});

describe("parsePayload", () => {
  it("parses a well formed payload", () => {
    const payload = parsePayload(
      '{"success":true,"source":"a.cps","phase":"semantic","diagnostics":[]}'
    );
    assert.equal(payload.success, true);
    assert.equal(payload.phase, "semantic");
  });

  it("rejects an empty output", () => {
    assert.throws(() => parsePayload("   "), /ninguna salida/);
  });

  it("rejects output that is not JSON", () => {
    assert.throws(() => parsePayload("Traceback (most recent call last)"), /no es JSON/);
  });

  it("rejects JSON without diagnostics", () => {
    assert.throws(() => parsePayload('{"success":true}'), /forma esperada/);
  });
});

describe("describeFailure", () => {
  it("treats 0 and 1 as normal outcomes", () => {
    assert.equal(describeFailure(0, "", "python3", "Driver.py"), undefined);
    assert.equal(describeFailure(1, "", "python3", "Driver.py"), undefined);
  });

  it("explains a missing file", () => {
    const message = describeFailure(2, "", "python3", "Driver.py");
    assert.match(String(message), /compilerPath/);
  });

  it("explains a missing ANTLR runtime", () => {
    const stderr = "ModuleNotFoundError: No module named 'antlr4'";
    const message = describeFailure(3, stderr, "python3", "Driver.py");
    assert.match(String(message), /pip install antlr4-python3-runtime==4\.13\.1/);
  });

  it("explains a missing driver", () => {
    const stderr = "python3: can't open file 'Driver.py'";
    const message = describeFailure(2, stderr, "python3", "Driver.py");
    assert.match(String(message), /compilerPath/);
  });
});

describe("describeSpawnFailure", () => {
  it("explains a missing interpreter", () => {
    const error = Object.assign(new Error("spawn python3 ENOENT"), { code: "ENOENT" });
    const message = describeSpawnFailure(error, "python3");
    assert.match(message, /pythonPath/);
  });
});

describe("toZeroBased", () => {
  it("subtracts one from the line and the column", () => {
    assert.deepEqual(toZeroBased(58, 32), { line: 57, character: 31 });
  });

  it("never returns a negative position", () => {
    assert.deepEqual(toZeroBased(0, 0), { line: 0, character: 0 });
  });
});

describe("summarize", () => {
  const base = { success: true, source: "a.cps", phase: "semantic", diagnostics: [] };

  it("reports a clean analysis", () => {
    const summary = summarize(base, "a.cps");
    assert.equal(summary.errors, 0);
    assert.match(summary.text, /sin errores/);
  });

  it("counts errors and warnings separately", () => {
    const summary = summarize(
      {
        ...base,
        success: false,
        diagnostics: [
          { code: "SEM105", phase: "semantic", severity: "error", message: "", line: 1, column: 1 },
          { code: "SEM604", phase: "semantic", severity: "warning", message: "", line: 2, column: 1 },
        ],
      },
      "a.cps"
    );
    assert.equal(summary.errors, 1);
    assert.equal(summary.warnings, 1);
    assert.match(summary.text, /1 error, 1 advertencia/);
  });
});

describe("renderSymbols", () => {
  const table = {
    scopes: {
      kind: "global",
      name: "global",
      qualifiedName: "global",
      line: 1,
      column: 1,
      symbols: [
        {
          name: "total",
          category: "variable",
          type: "integer",
          line: 1,
          column: 5,
          mutable: true,
        },
      ],
      children: [],
    },
    classes: [],
  };

  it("renders the scope tree", () => {
    const html = renderSymbols(table, "a.cps");
    assert.match(html, /<!DOCTYPE html>/);
    assert.match(html, /total/);
    assert.match(html, /integer/);
    assert.match(html, /\[global\]/);
  });

  it("escapes the file name", () => {
    assert.match(renderSymbols(table, "<script>.cps"), /&lt;script&gt;/);
  });

  it("escapes every unsafe character", () => {
    assert.equal(escapeHtml('<a href="x">&</a>'), "&lt;a href=&quot;x&quot;&gt;&amp;&lt;/a&gt;");
  });
});
