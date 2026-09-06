/** Maps compiler diagnostics to entries of the Problems panel. */

import * as vscode from "vscode";

import { CompiscriptDiagnostic, CompiscriptPayload, toZeroBased } from "./protocol";

/**
 * The compiler emits 1-based lines and columns; the VS Code API is 0-based on
 * both axes, so one is subtracted from each.
 */
export function toRange(
  document: vscode.TextDocument,
  diagnostic: CompiscriptDiagnostic
): vscode.Range {
  const zero = toZeroBased(diagnostic.line, diagnostic.column);
  const line = Math.min(zero.line, document.lineCount - 1);
  const text = document.lineAt(line);
  const column = Math.min(zero.character, text.text.length);
  const start = new vscode.Position(line, column);
  const word = document.getWordRangeAtPosition(start);
  if (word && word.start.isEqual(start)) {
    return word;
  }
  const end = new vscode.Position(line, Math.max(column + 1, text.text.length));
  return new vscode.Range(start, end);
}

export function toSeverity(diagnostic: CompiscriptDiagnostic): vscode.DiagnosticSeverity {
  return diagnostic.severity === "warning"
    ? vscode.DiagnosticSeverity.Warning
    : vscode.DiagnosticSeverity.Error;
}

export function toDiagnostic(
  document: vscode.TextDocument,
  diagnostic: CompiscriptDiagnostic
): vscode.Diagnostic {
  const entry = new vscode.Diagnostic(
    toRange(document, diagnostic),
    diagnostic.message,
    toSeverity(diagnostic)
  );
  entry.code = diagnostic.code;
  entry.source = `compiscript (${diagnostic.phase})`;
  return entry;
}

/** Replace the diagnostics of a document; stale entries never survive. */
export function publish(
  collection: vscode.DiagnosticCollection,
  document: vscode.TextDocument,
  payload: CompiscriptPayload
): void {
  const entries = payload.diagnostics.map((item) => toDiagnostic(document, item));
  collection.set(document.uri, entries);
}
