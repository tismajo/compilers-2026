/**
 * Runs `program/Driver.py` and returns its output.
 *
 * The process is spawned without a shell and every argument travels as its own
 * array entry, so paths with spaces work on every platform. Docker is never
 * required: the extension only needs a Python interpreter with the ANTLR
 * runtime installed.
 */

import { execFile } from "node:child_process";

import {
  CompiscriptPayload,
  DriverOptions,
  buildArgs,
  describeFailure,
  describeSpawnFailure,
  parsePayload,
} from "./protocol";

/** Trees and symbol tables are large; the default 1 MB buffer is not enough. */
const MAX_BUFFER = 64 * 1024 * 1024;

export interface RunResult {
  exitCode: number;
  stdout: string;
  stderr: string;
}

export interface RunSettings {
  pythonPath: string;
  compilerPath: string;
  cwd: string;
}

export class CompilerError extends Error {}

export function runDriver(settings: RunSettings, options: DriverOptions): Promise<RunResult> {
  const args = buildArgs(options);
  return new Promise((resolve, reject) => {
    execFile(
      settings.pythonPath,
      args,
      { cwd: settings.cwd, maxBuffer: MAX_BUFFER, windowsHide: true },
      (error, stdout, stderr) => {
        if (!error) {
          resolve({ exitCode: 0, stdout, stderr });
          return;
        }
        // execFile reports the exit code as a number and a spawn failure
        // (missing interpreter, no permissions) as a string code.
        const failure = error as NodeJS.ErrnoException & { code?: number | string };
        if (typeof failure.code === "string") {
          reject(new CompilerError(describeSpawnFailure(failure, settings.pythonPath)));
          return;
        }
        resolve({ exitCode: typeof failure.code === "number" ? failure.code : 1, stdout, stderr });
      }
    );
  });
}

/** Analyze a file and return the parsed payload. */
export async function analyze(
  settings: RunSettings,
  sourcePath: string,
  extras: Partial<DriverOptions> = {}
): Promise<CompiscriptPayload> {
  const result = await runDriver(settings, {
    compilerPath: settings.compilerPath,
    sourcePath,
    format: "json",
    ...extras,
  });
  const failure = describeFailure(
    result.exitCode,
    result.stderr,
    settings.pythonPath,
    settings.compilerPath
  );
  if (failure) {
    throw new CompilerError(failure);
  }
  return parsePayload(result.stdout);
}

/** Render the tree as a self-contained document (`html` or `svg`). */
export async function renderTree(
  settings: RunSettings,
  sourcePath: string,
  format: "html" | "svg"
): Promise<string> {
  const result = await runDriver(settings, {
    compilerPath: settings.compilerPath,
    sourcePath,
    format: "text",
    tree: format,
  });
  const failure = describeFailure(
    result.exitCode,
    result.stderr,
    settings.pythonPath,
    settings.compilerPath
  );
  if (failure) {
    throw new CompilerError(failure);
  }
  if (!result.stdout.trim()) {
    throw new CompilerError("El compilador no devolvió el árbol.");
  }
  return result.stdout;
}
