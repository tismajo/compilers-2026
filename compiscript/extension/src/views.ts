/** Webview panels for the parse tree and the symbol table. */

import * as vscode from "vscode";

export class PanelRegistry {
  private readonly panels = new Map<string, vscode.WebviewPanel>();

  show(id: string, title: string, html: string): vscode.WebviewPanel {
    const existing = this.panels.get(id);
    const panel =
      existing ??
      vscode.window.createWebviewPanel(`compiscript.${id}`, title, vscode.ViewColumn.Beside, {
        enableScripts: true,
        retainContextWhenHidden: true,
      });
    if (!existing) {
      panel.onDidDispose(() => this.panels.delete(id));
      this.panels.set(id, panel);
    }
    panel.title = title;
    panel.webview.html = html;
    panel.reveal(panel.viewColumn, true);
    return panel;
  }

  dispose(): void {
    for (const panel of this.panels.values()) {
      panel.dispose();
    }
    this.panels.clear();
  }
}
