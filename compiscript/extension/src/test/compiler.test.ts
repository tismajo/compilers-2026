/**
 * Integration tests: the extension really runs `program/Driver.py`.
 *
 * They are skipped when no interpreter with the ANTLR runtime is available, so
 * the suite still passes on a machine without the Python environment.
 */

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import * as path from "node:path";
import { describe, it } from "node:test";

import { RunSettings, analyze, renderTree } from "../compiler";

const ROOT = path.resolve(__dirname, "..", "..", "..");
const DRIVER = path.join(ROOT, "program", "Driver.py");
const PROGRAM = path.join(ROOT, "program", "program.cps");

function findPython(): string | undefined {
  const candidates = [
    path.join(ROOT, ".venv", "Scripts", "python.exe"),
    path.join(ROOT, ".venv", "bin", "python"),
    "python3",
    "python",
  ];
  for (const candidate of candidates) {
    if (candidate.includes(path.sep) && !existsSync(candidate)) {
      continue;
    }
    try {
      execFileSync(candidate, ["-c", "import antlr4"], { stdio: "ignore" });
      return candidate;
    } catch {
      continue;
    }
  }
  return undefined;
}

const python = findPython();
const settings: RunSettings = {
  pythonPath: python ?? "python3",
  compilerPath: DRIVER,
  cwd: ROOT,
};

describe("compiler integration", { skip: python ? false : "sin Python con antlr4" }, () => {
  it("analyzes the official program", async () => {
    const payload = await analyze(settings, PROGRAM);
    assert.equal(payload.success, true);
    assert.equal(payload.phase, "semantic");
    assert.equal(payload.diagnostics.length, 1);
    assert.equal(payload.diagnostics[0].severity, "warning");
    assert.equal(payload.diagnostics[0].code, "SEM604");
  });

  it("reports semantic errors with their position", async () => {
    const source = path.join(ROOT, "tests", "fixtures", "invalid", "errores_multiples.cps");
    const payload = await analyze(settings, source);
    assert.equal(payload.success, false);
    const codes = payload.diagnostics.map((item) => item.code);
    assert.ok(codes.includes("SEM201"));
    for (const diagnostic of payload.diagnostics) {
      assert.ok(diagnostic.line > 0);
      assert.ok(diagnostic.column > 0);
    }
  });

  it("returns the symbol table when asked", async () => {
    const payload = await analyze(settings, PROGRAM, { symbols: "json" });
    assert.ok(payload.symbols);
  });

  it("fails with a readable message when the driver is missing", async () => {
    const broken: RunSettings = { ...settings, compilerPath: path.join(ROOT, "no-existe.py") };
    await assert.rejects(() => analyze(broken, PROGRAM), /compilerPath/);
  });

  it("fails with a readable message when Python is missing", async () => {
    const broken: RunSettings = { ...settings, pythonPath: "python-que-no-existe" };
    await assert.rejects(() => analyze(broken, PROGRAM), /pythonPath/);
  });

  it("renders the interactive tree", async () => {
    const html = await renderTree(settings, PROGRAM, "html");
    assert.ok(html.startsWith("<!DOCTYPE html>"));
    assert.ok(html.includes("<details"));
  });

  it("renders the SVG export", async () => {
    const svg = await renderTree(settings, PROGRAM, "svg");
    assert.ok(svg.startsWith("<svg"));
  });
});
