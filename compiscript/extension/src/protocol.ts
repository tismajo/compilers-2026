/**
 * Contract between the extension and `program/Driver.py`.
 *
 * Nothing here imports `vscode`, so the whole protocol layer is unit tested
 * with the Node test runner.
 */

export type Severity = "error" | "warning";

export interface CompiscriptDiagnostic {
  code: string;
  phase: string;
  severity: Severity;
  message: string;
  /** 1-based, as emitted by the compiler. */
  line: number;
  /** 1-based, as emitted by the compiler. */
  column: number;
}

export interface CompiscriptPayload {
  success: boolean;
  source: string;
  phase: string;
  diagnostics: CompiscriptDiagnostic[];
  tree?: unknown;
  symbols?: unknown;
}

/** Exit codes of the CLI. Anything else means the process itself failed. */
export const EXIT_OK = 0;
export const EXIT_DIAGNOSTICS = 1;
export const EXIT_MISSING_FILE = 2;

export interface DriverOptions {
  compilerPath: string;
  sourcePath: string;
  format?: "text" | "json";
  tree?: "none" | "lisp" | "json" | "html" | "svg";
  symbols?: "none" | "text" | "json";
}

/**
 * Expand `${workspaceFolder}` in a setting.
 *
 * Paths keep their spaces: every argument travels as a separate array entry
 * and the process is spawned without a shell.
 */
export function resolveSetting(value: string, workspaceFolder: string): string {
  return value.split("${workspaceFolder}").join(workspaceFolder).trim();
}

/** Argument list for the driver; never a joined command line. */
export function buildArgs(options: DriverOptions): string[] {
  const args = [options.compilerPath, options.sourcePath];
  args.push("--format", options.format ?? "json");
  if (options.tree && options.tree !== "none") {
    args.push("--tree", options.tree);
  }
  if (options.symbols && options.symbols !== "none") {
    args.push("--symbols", options.symbols);
  }
  return args;
}

/** Parse the JSON payload; throws a readable error when it is not JSON. */
export function parsePayload(stdout: string): CompiscriptPayload {
  const text = stdout.trim();
  if (!text) {
    throw new Error("El compilador no devolvió ninguna salida.");
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error(`El compilador devolvió una salida que no es JSON:\n${text.slice(0, 400)}`);
  }
  const payload = parsed as CompiscriptPayload;
  if (typeof payload !== "object" || payload === null || !Array.isArray(payload.diagnostics)) {
    throw new Error("El JSON del compilador no tiene la forma esperada.");
  }
  return payload;
}

/**
 * Turn a failed run into an actionable message.
 *
 * Returns `undefined` when the exit code is one the CLI defines, because those
 * are normal outcomes and not failures of the tooling.
 */
export function describeFailure(
  exitCode: number,
  stderr: string,
  pythonPath: string,
  compilerPath: string
): string | undefined {
  if (exitCode === EXIT_OK || exitCode === EXIT_DIAGNOSTICS) {
    return undefined;
  }
  if (exitCode === EXIT_MISSING_FILE) {
    return `El compilador no encontró el archivo. Revisa 'compiscript.compilerPath': ${compilerPath}`;
  }
  if (stderr.includes("No module named 'antlr4'")) {
    return (
      "Falta el runtime de ANTLR. Instálalo con: " +
      `${pythonPath} -m pip install antlr4-python3-runtime==4.13.1`
    );
  }
  if (stderr.includes("No such file or directory") || stderr.includes("can't open file")) {
    return `No se encontró 'Driver.py'. Revisa 'compiscript.compilerPath': ${compilerPath}`;
  }
  const detail = stderr.trim().split("\n").slice(-3).join("\n");
  return `El compilador terminó con código ${exitCode}.\n${detail}`;
}

/** Message shown when the interpreter itself cannot be started. */
export function describeSpawnFailure(error: NodeJS.ErrnoException, pythonPath: string): string {
  if (error.code === "ENOENT") {
    return (
      `No se pudo ejecutar Python ('${pythonPath}'). ` +
      "Configura 'compiscript.pythonPath' con la ruta del intérprete, " +
      "por ejemplo ${workspaceFolder}/.venv/Scripts/python.exe"
    );
  }
  return `No se pudo ejecutar el compilador: ${error.message}`;
}

/**
 * The compiler emits 1-based lines and columns; the VS Code API is 0-based on
 * both axes. Never let a position go negative.
 */
export function toZeroBased(line: number, column: number): { line: number; character: number } {
  return { line: Math.max(0, line - 1), character: Math.max(0, column - 1) };
}

export interface Summary {
  errors: number;
  warnings: number;
  text: string;
}

/** One-line compilation summary. Docker is never involved. */
export function summarize(payload: CompiscriptPayload, fileName: string): Summary {
  const errors = payload.diagnostics.filter((item) => item.severity === "error").length;
  const warnings = payload.diagnostics.filter((item) => item.severity === "warning").length;
  const phase = payload.phase === "semantic" ? "sintáctico y semántico" : "sintáctico";
  const state = errors === 0 ? "sin errores" : `${errors} ${plural(errors, "error", "errores")}`;
  const extra = warnings > 0 ? `, ${warnings} ${plural(warnings, "advertencia", "advertencias")}` : "";
  return {
    errors,
    warnings,
    text: `${fileName}: análisis ${phase} ${state}${extra}.`,
  };
}

function plural(count: number, singular: string, plural: string): string {
  return count === 1 ? singular : plural;
}
