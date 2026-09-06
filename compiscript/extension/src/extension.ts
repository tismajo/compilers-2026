/** Entry point of the Compiscript extension. */

import * as path from "node:path";
import * as vscode from "vscode";

import { CompilerError, RunSettings, analyze, renderTree } from "./compiler";
import { publish } from "./diagnostics";
import { CompiscriptPayload, resolveSetting, summarize } from "./protocol";
import { renderSymbols } from "./render";
import { PanelRegistry } from "./views";

const LANGUAGE_ID = "compiscript";

let collection: vscode.DiagnosticCollection;
let output: vscode.OutputChannel;
let status: vscode.StatusBarItem;
const panels = new PanelRegistry();

export function activate(context: vscode.ExtensionContext): void {
  collection = vscode.languages.createDiagnosticCollection(LANGUAGE_ID);
  output = vscode.window.createOutputChannel("Compiscript");
  status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);

  context.subscriptions.push(
    collection,
    output,
    status,
    vscode.commands.registerCommand("compiscript.analyze", () => analyzeActiveDocument(true)),
    vscode.commands.registerCommand("compiscript.showTree", showTree),
    vscode.commands.registerCommand("compiscript.showSymbols", showSymbols),
    vscode.workspace.onDidSaveTextDocument(onSave),
    vscode.workspace.onDidCloseTextDocument((document) => collection.delete(document.uri))
  );
}

export function deactivate(): void {
  panels.dispose();
}

function onSave(document: vscode.TextDocument): void {
  const enabled = vscode.workspace
    .getConfiguration(LANGUAGE_ID)
    .get<boolean>("analyzeOnSave", true);
  if (enabled && document.languageId === LANGUAGE_ID) {
    void analyzeDocument(document, false);
  }
}

/** Resolve the settings for the folder that owns the document. */
function settingsFor(document: vscode.TextDocument): RunSettings {
  const folder = vscode.workspace.getWorkspaceFolder(document.uri);
  const root = folder ? folder.uri.fsPath : path.dirname(document.uri.fsPath);
  const configuration = vscode.workspace.getConfiguration(LANGUAGE_ID, document.uri);
  return {
    pythonPath: resolveSetting(configuration.get<string>("pythonPath", "python3"), root),
    compilerPath: resolveSetting(
      configuration.get<string>("compilerPath", "${workspaceFolder}/program/Driver.py"),
      root
    ),
    cwd: root,
  };
}

function activeCompiscriptDocument(): vscode.TextDocument | undefined {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== LANGUAGE_ID) {
    void vscode.window.showWarningMessage("Abre un archivo .cps para usar este comando.");
    return undefined;
  }
  return editor.document;
}

async function analyzeActiveDocument(verbose: boolean): Promise<CompiscriptPayload | undefined> {
  const document = activeCompiscriptDocument();
  if (!document) {
    return undefined;
  }
  return analyzeDocument(document, verbose);
}

async function analyzeDocument(
  document: vscode.TextDocument,
  verbose: boolean,
  extras: { symbols?: "json" } = {}
): Promise<CompiscriptPayload | undefined> {
  if (document.isDirty) {
    await document.save();
  }
  const settings = settingsFor(document);
  try {
    const payload = await analyze(settings, document.uri.fsPath, extras);
    publish(collection, document, payload);
    report(payload, document, verbose);
    return payload;
  } catch (error) {
    collection.delete(document.uri);
    reportFailure(error);
    return undefined;
  }
}

function report(
  payload: CompiscriptPayload,
  document: vscode.TextDocument,
  verbose: boolean
): void {
  const name = path.basename(document.uri.fsPath);
  const summary = summarize(payload, name);
  const configuration = vscode.workspace.getConfiguration(LANGUAGE_ID);
  if (!configuration.get<boolean>("showSummary", true)) {
    return;
  }
  output.appendLine(summary.text);
  for (const diagnostic of payload.diagnostics) {
    output.appendLine(
      `  ${diagnostic.line}:${diagnostic.column} ${diagnostic.severity} ` +
        `${diagnostic.code}: ${diagnostic.message}`
    );
  }
  status.text = summary.errors > 0 ? `$(error) ${summary.text}` : `$(check) ${summary.text}`;
  status.tooltip = "Resumen del último análisis de Compiscript";
  status.show();
  if (verbose && summary.errors > 0) {
    void vscode.window.showErrorMessage(summary.text);
  } else if (verbose) {
    void vscode.window.showInformationMessage(summary.text);
  }
}

function reportFailure(error: unknown): void {
  const message = error instanceof CompilerError ? error.message : String(error);
  output.appendLine(message);
  status.hide();
  void vscode.window.showErrorMessage(message, "Ver detalles").then((choice) => {
    if (choice) {
      output.show(true);
    }
  });
}

async function showTree(): Promise<void> {
  const document = activeCompiscriptDocument();
  if (!document) {
    return;
  }
  if (document.isDirty) {
    await document.save();
  }
  const settings = settingsFor(document);
  try {
    const html = await renderTree(settings, document.uri.fsPath, "html");
    const name = path.basename(document.uri.fsPath);
    panels.show("tree", `Árbol · ${name}`, html);
  } catch (error) {
    reportFailure(error);
  }
}

async function showSymbols(): Promise<void> {
  const document = activeCompiscriptDocument();
  if (!document) {
    return;
  }
  const payload = await analyzeDocument(document, false, { symbols: "json" });
  if (!payload) {
    return;
  }
  if (!payload.symbols) {
    void vscode.window.showWarningMessage(
      "El archivo tiene errores sintácticos, así que no hay tabla de símbolos."
    );
    return;
  }
  const name = path.basename(document.uri.fsPath);
  panels.show("symbols", `Símbolos · ${name}`, renderSymbols(payload.symbols, name));
}
