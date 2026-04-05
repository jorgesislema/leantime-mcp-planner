import * as vscode from 'vscode';
import * as http from 'http';
import * as https from 'https';
import { URL } from 'url';
import * as os from 'os';

function httpGetJson(urlStr: string): Promise<any> {
  return new Promise((resolve, reject) => {
    try {
      const url = new URL(urlStr);
      const isHttps = url.protocol === 'https:';
      const client = isHttps ? https : http;
      const opts: any = {
        hostname: url.hostname,
        port: url.port || (isHttps ? 443 : 80),
        path: url.pathname + (url.search || ''),
        method: 'GET'
      };
      const req = client.request(opts, (res: any) => {
        let data = '';
        res.on('data', (chunk: any) => (data += chunk));
        res.on('end', () => {
          try {
            resolve(JSON.parse(data));
          } catch (e) {
            // if empty or non-json, resolve with raw
            if (!data) resolve(null);
            else reject(e);
          }
        });
      });
      req.on('error', (err: any) => reject(err));
      req.end();
    } catch (err) {
      reject(err);
    }
  });
}

function httpPostJson(urlStr: string, method: string = 'POST', body?: any): Promise<any> {
  return new Promise((resolve, reject) => {
    try {
      const url = new URL(urlStr);
      const isHttps = url.protocol === 'https:';
      const client = isHttps ? https : http;
      const payload = body ? JSON.stringify(body) : '';
      const opts: any = {
        hostname: url.hostname,
        port: url.port || (isHttps ? 443 : 80),
        path: url.pathname + (url.search || ''),
        method: method,
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(payload || '')
        }
      };
      const req = client.request(opts, (res: any) => {
        let data = '';
        res.on('data', (chunk: any) => (data += chunk));
        res.on('end', () => {
          if (!data) return resolve(null);
          try {
            resolve(JSON.parse(data));
          } catch (e) {
            resolve(data);
          }
        });
      });
      req.on('error', (err: any) => reject(err));
      if (payload) req.write(payload);
      req.end();
    } catch (err) {
      reject(err);
    }
  });
}

let statusBar: vscode.StatusBarItem | undefined;
let intervalHandle: NodeJS.Timeout | undefined;
let tasksProvider: TasksProvider | undefined;

export function activate(context: vscode.ExtensionContext) {
  const config = vscode.workspace.getConfiguration('leantime-mcp');
  const bridgeUrl = config.get<string>('bridgeUrl', 'http://localhost:8080');
  const projectId = config.get<number>('projectId', 1);
  const pollInterval = Math.max(10, config.get<number>('pollInterval', 60));

  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBar.text = 'Leantime: connecting...';
  statusBar.show();

  const refresh = async () => {
    try {
      const url = `${bridgeUrl.replace(/\/$/, '')}/tasks?project_id=${projectId}`;
      const data = await httpGetJson(url);
      const count = Array.isArray(data) ? data.length : (data?.value?.length ?? 0);
      statusBar!.text = `Leantime: ${count} tasks`;
      statusBar!.tooltip = `Monitoreando proyecto ${projectId} — ${bridgeUrl}`;
    } catch (err) {
      statusBar!.text = 'Leantime: error';
      statusBar!.tooltip = String(err);
    }
  };

  // Auto-detect or prompt for projectId if not set
  (async () => {
    try {
      const cfg = vscode.workspace.getConfiguration('leantime-mcp');
      const configured = cfg.get<number>('projectId', 0);
      if (!configured) {
        const projectsUrl = `${bridgeUrl.replace(/\/$/, '')}/projects`;
        const projects = await httpGetJson(projectsUrl);
        if (Array.isArray(projects) && projects.length > 0) {
          if (projects.length === 1) {
            await cfg.update('projectId', projects[0].id, vscode.ConfigurationTarget.Workspace);
          } else {
            const picks = projects.map((p: any) => ({ label: String(p.id), description: p.name || p.headline || '', id: p.id }));
            const sel = await vscode.window.showQuickPick(picks, { placeHolder: 'Selecciona el Project ID para este workspace' });
            if (sel?.id) {
              await cfg.update('projectId', Number(sel.id), vscode.ConfigurationTarget.Workspace);
            }
          }
        }
      }
    } catch (e) {
      // ignore detection errors
      console.warn('Leantime MCP: project auto-detect failed', e);
    }
  })();

  // initial refresh
  void refresh();
  intervalHandle = setInterval(() => void refresh(), pollInterval * 1000);

  const disposable = vscode.commands.registerCommand('leantime-mcp.refresh', () => void refresh());
  const openCmd = vscode.commands.registerCommand('leantime-mcp.open', async () => {
    try {
      const cfg = vscode.workspace.getConfiguration('leantime-mcp');
      const pid = cfg.get<number>('projectId', projectId) || projectId;
      const openUrl = `${bridgeUrl.replace(/\/$/, '')}/projects/${pid}`;
      await vscode.env.openExternal(vscode.Uri.parse(openUrl));
    } catch (e) {
      vscode.window.showErrorMessage('No se pudo abrir el proyecto en el navegador: ' + String(e));
    }
  });
  context.subscriptions.push(disposable, statusBar);
  context.subscriptions.push(openCmd);

  // Register Tasks TreeView provider
  tasksProvider = new TasksProvider(bridgeUrl, projectId);
  const view = vscode.window.createTreeView('leantimeMcpView', { treeDataProvider: tasksProvider });
  context.subscriptions.push(view);

  // Command to open/show a task
  const openTaskCmd = vscode.commands.registerCommand('leantime-mcp.openTask', async (task: any) => {
    if (!task) return;
    const detail = `#${task.id} — ${task.headline}\n\n${task.description || ''}`;
    const pick = await vscode.window.showInformationMessage(detail, 'Open in Browser', 'Copy ID', 'Mark Complete', 'Reopen');
    if (pick === 'Open in Browser') {
      try {
        // Open project task list (bridge URL) — user can configure Leantime web url in settings if desired
        const cfg = vscode.workspace.getConfiguration('leantime-mcp');
        const bridge = cfg.get<string>('bridgeUrl', bridgeUrl);
        // open project tasks page as fallback
        const openUrl = `${bridge.replace(/\/$/, '')}/tasks?project_id=${cfg.get<number>('projectId', projectId)}`;
        await vscode.env.openExternal(vscode.Uri.parse(openUrl));
      } catch (e) {
        vscode.window.showErrorMessage('No se pudo abrir en el navegador: ' + String(e));
      }
    } else if (pick === 'Copy ID') {
      await vscode.env.clipboard.writeText(String(task.id));
      vscode.window.showInformationMessage('Task id copiado al portapapeles');
    } else if (pick === 'Mark Complete') {
      try {
        const cfg = vscode.workspace.getConfiguration('leantime-mcp');
        const bridge = cfg.get<string>('bridgeUrl', bridgeUrl).replace(/\/$/, '');
        // Try a dedicated complete endpoint first, fallback to PATCH update
        const completeUrl = `${bridge}/tasks/${task.id}/complete`;
        try {
          await httpPostJson(completeUrl, 'POST');
        } catch (e) {
          // fallback: try to PATCH task status
          const patchUrl = `${bridge}/tasks/${task.id}`;
          await httpPostJson(patchUrl, 'PATCH', { status: 'done' });
        }
        vscode.window.showInformationMessage(`Tarea #${task.id} marcada como completada`);
        try { tasksProvider?.refresh(); } catch {}
      } catch (e) {
        vscode.window.showErrorMessage('Error marcando la tarea como completada: ' + String(e));
      }
    } else if (pick === 'Reopen') {
      try {
        const cfg = vscode.workspace.getConfiguration('leantime-mcp');
        const bridge = cfg.get<string>('bridgeUrl', bridgeUrl).replace(/\/$/, '');
        const reopenUrl = `${bridge}/tasks/${task.id}/reopen`;
        try {
          await httpPostJson(reopenUrl, 'POST');
        } catch (e) {
          const patchUrl = `${bridge}/tasks/${task.id}`;
          await httpPostJson(patchUrl, 'PATCH', { status: 'open' });
        }
        vscode.window.showInformationMessage(`Tarea #${task.id} reabierta`);
        try { tasksProvider?.refresh(); } catch {}
      } catch (e) {
        vscode.window.showErrorMessage('Error reabriendo la tarea: ' + String(e));
      }
    }
  });
  context.subscriptions.push(openTaskCmd);
}

class TasksProvider implements vscode.TreeDataProvider<any> {
  private _onDidChangeTreeData: vscode.EventEmitter<any | undefined> = new vscode.EventEmitter<any | undefined>();
  readonly onDidChangeTreeData: vscode.Event<any | undefined> = this._onDidChangeTreeData.event;

  constructor(private bridgeUrl: string, private projectId: number) {}

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: any): vscode.TreeItem {
    const ti = new vscode.TreeItem(element.headline || `#${element.id}`, vscode.TreeItemCollapsibleState.None);
    ti.tooltip = element.description || '';
    ti.command = { command: 'leantime-mcp.openTask', title: 'Open Task', arguments: [element] };
    return ti;
  }

  async getChildren(element?: any): Promise<any[]> {
    try {
      const url = `${this.bridgeUrl.replace(/\/$/, '')}/tasks?project_id=${this.projectId}`;
      const data = await httpGetJson(url);
      const list = Array.isArray(data) ? data : (data?.value ?? []);
      // filter tasks for 'today' by date field (YYYY-MM-DD)
      const today = new Date();
      const y = today.getFullYear();
      const m = String(today.getMonth() + 1).padStart(2, '0');
      const d = String(today.getDate()).padStart(2, '0');
      const todayPrefix = `${y}-${m}-${d}`;
      const todayTasks = list.filter((t: any) => String(t.date || '').startsWith(todayPrefix));
      return todayTasks;
    } catch (e) {
      return [];
    }
  }
}

export function deactivate() {
  if (intervalHandle) {
    clearInterval(intervalHandle);
    intervalHandle = undefined;
  }
  if (statusBar) {
    statusBar.dispose();
    statusBar = undefined;
  }
}
