/** Pure renderers for the webviews; no `vscode` import, so they are testable. */

interface ScopePayload {
  kind: string;
  name: string;
  qualifiedName: string;
  line: number;
  column: number;
  symbols: SymbolPayload[];
  children: ScopePayload[];
}

interface SymbolPayload {
  name: string;
  category: string;
  type: string;
  line: number;
  column: number;
  mutable: boolean;
}

interface SymbolsPayload {
  scopes: ScopePayload;
  classes: unknown[];
}

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Render the symbol table exported by `--symbols json`. */
export function renderSymbols(payload: unknown, fileName: string): string {
  const symbols = payload as SymbolsPayload;
  const body = symbols?.scopes ? renderScope(symbols.scopes) : "<p>Sin tabla de símbolos.</p>";
  return `<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>Tabla de símbolos</title>
<style>
body { font: 13px/1.5 ui-monospace, Consolas, monospace; padding: 16px; }
h1 { font-size: 15px; margin: 0 0 12px; }
ul { list-style: none; margin: 0; padding-left: 18px; }
details > summary { cursor: pointer; font-weight: 600; }
.kind { opacity: .6; margin-right: 6px; }
.type { opacity: .8; font-style: italic; }
.pos { opacity: .5; font-size: 11px; margin-left: 6px; }
.const { color: #a06000; }
table { border-collapse: collapse; margin: 4px 0 8px; }
td { padding: 1px 10px 1px 0; vertical-align: top; }
</style></head>
<body><h1>Tabla de símbolos · ${escapeHtml(fileName)}</h1>${body}</body></html>`;
}

interface TacPayload {
  text?: string;
}

/** Render the TAC exported by `--tac json`.
 *
 * Reuses the text Python already rendered (`TacProgram.render()`) instead of
 * re-implementing `Quad.render()`'s op-to-text rules a second time in
 * TypeScript, which is exactly the kind of duplication that caused a bug
 * between the checker and the generator during the TAC work itself.
 */
export function renderTac(payload: unknown, fileName: string): string {
  const tac = payload as TacPayload | undefined;
  const blocks = (tac?.text ?? "").split("\n\n").filter((block) => block.trim().length > 0);
  const body = blocks.length
    ? blocks.map((block) => renderTacBlock(block)).join("")
    : "<p>Sin código intermedio.</p>";
  return `<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>Código intermedio</title>
<style>
body { font: 13px/1.5 ui-monospace, Consolas, monospace; padding: 16px; }
h1 { font-size: 15px; margin: 0 0 12px; }
details > summary { cursor: pointer; font-weight: 600; margin: 6px 0; }
pre { margin: 4px 0 12px 18px; white-space: pre; }
</style></head>
<body><h1>Código intermedio · ${escapeHtml(fileName)}</h1>${body}</body></html>`;
}

function renderTacBlock(block: string): string {
  const lines = block.split("\n");
  const summary = lines[0] ?? "";
  const rest = lines.slice(1).join("\n");
  return `<details open><summary>${escapeHtml(summary)}</summary><pre>${escapeHtml(rest)}</pre></details>`;
}

function renderScope(scope: ScopePayload): string {
  const rows = scope.symbols
    .map(
      (symbol) => `<tr>
<td class="kind">${escapeHtml(symbol.category)}</td>
<td>${escapeHtml(symbol.name)}</td>
<td class="type">${escapeHtml(symbol.type)}</td>
<td class="${symbol.mutable ? "" : "const"}">${symbol.mutable ? "" : "constante"}</td>
<td class="pos">${symbol.line}:${symbol.column}</td>
</tr>`
    )
    .join("");
  const table = rows ? `<table>${rows}</table>` : "";
  const children = scope.children.map((child) => `<li>${renderScope(child)}</li>`).join("");
  const nested = children ? `<ul>${children}</ul>` : "";
  return `<details open><summary><span class="kind">[${escapeHtml(scope.kind)}]</span>${escapeHtml(
    scope.qualifiedName
  )}</summary>${table}${nested}</details>`;
}
