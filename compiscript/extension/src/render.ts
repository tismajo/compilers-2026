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
