import { TermboxAPI } from './api.js';
import { ansiToHtml } from './ansi_parser.js';
import { renderLineageGraph } from './lineage_graph.js';
import { openTemplatesDrawer } from './templates_drawer.js';
import { renderArtifactsViewer } from './artifact_viewer.js';
import { openDiffModal } from './diff_viewer.js';
import { openBatchRunner } from './batch_runner.js';

let currentFilter = '';
let currentSearch = '';
let cachedRuns = [];
let activeStream = null;

export function streamLiveLogs(runId, terminalElement) {
  if (activeStream) {
    activeStream.close();
    activeStream = null;
  }
  const evtSource = new EventSource(`/runs/${runId}/events`);
  activeStream = evtSource;
  evtSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data.type === 'step_finish' && data.payload.stdout) {
        terminalElement.innerHTML += ansiToHtml(data.payload.stdout);
        terminalElement.scrollTop = terminalElement.scrollHeight;
      }
      if (data.type === 'run_finish') {
        evtSource.close();
        activeStream = null;
      }
    } catch (err) {
      console.error('Error handling SSE event', err);
    }
  };
  return evtSource;
}

export async function checkHealth() {
  try {
    const data = await TermboxAPI.getHealth();
    const badge = document.getElementById('daemon-status');
    if (!badge) return;
    if (data.docker_available) {
      badge.textContent = 'Docker Online';
      badge.className = 'badge-live';
    } else {
      badge.textContent = 'Mock Fallback Active';
      badge.style.background = 'rgba(245, 158, 11, 0.15)';
      badge.style.color = '#fbbf24';
      badge.style.borderColor = 'rgba(245, 158, 11, 0.3)';
    }
  } catch (e) {
    console.error('Health check failed', e);
  }
}

export async function fetchRuns() {
  try {
    const params = { limit: 100 };
    if (currentFilter) params.failure_mode = currentFilter;
    if (currentSearch) params.search = currentSearch;
    const data = await TermboxAPI.listRuns(params);
    cachedRuns = data.runs || [];
    renderRuns(cachedRuns);
    updateStats();
  } catch (e) {
    console.error('Failed to fetch runs', e);
  }
}

export function updateStats() {
  const total = document.getElementById('stat-total');
  const passed = document.getElementById('stat-passed');
  const assert = document.getElementById('stat-assert');
  const oomTimeout = document.getElementById('stat-oom-timeout');

  if (total) total.textContent = cachedRuns.length;
  if (passed) passed.textContent = cachedRuns.filter(r => r.failure_mode === 'PASSED').length;
  if (assert) assert.textContent = cachedRuns.filter(r => r.failure_mode === 'ASSERTION_FAILED').length;
  if (oomTimeout) oomTimeout.textContent = cachedRuns.filter(r => r.failure_mode === 'OOM_KILLED' || r.failure_mode === 'TIMEOUT').length;
}

export function renderRuns(runs) {
  const tbody = document.getElementById('runs-table-body');
  if (!tbody) return;
  if (!runs.length) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 32px;">No execution manifests found. Submit a task or click a preset above!</td></tr>`;
    return;
  }
  tbody.innerHTML = runs.map(run => {
    const modeBadge = run.failure_mode ? `<span class="badge badge-${run.failure_mode}">${run.failure_mode}</span>` : `<span class="badge badge-${run.status}">${run.status}</span>`;
    const lineageHtml = run.parent_run_id
      ? `<a href="javascript:window.termboxApp.inspectRun('${run.parent_run_id}')" class="lineage-badge" style="color:#60a5fa; font-size:11px;">Replay of ${run.parent_run_id.slice(-6)}</a>`
      : `<span style="color: #6b7280; font-size: 11px;">root (${run.replay_count} replays)</span>`;
    const dur = (run.duration_ms / 1000).toFixed(2) + 's';
    const dateStr = new Date(run.created_at).toLocaleTimeString();
    const shortCmd = run.main_cmd.length > 32 ? run.main_cmd.slice(0, 30) + '...' : run.main_cmd;

    return `
      <tr>
        <td class="mono"><strong><a href="javascript:window.termboxApp.inspectRun('${run.run_id}')" style="color: #60a5fa; text-decoration: none;">${run.run_id}</a></strong></td>
        <td>${lineageHtml}</td>
        <td><span class="badge badge-${run.status}">${run.status}</span></td>
        <td>${modeBadge}</td>
        <td class="mono" title="${escapeHtml(run.main_cmd)}">${escapeHtml(shortCmd)}</td>
        <td class="mono">${run.exit_code !== null ? run.exit_code : '-'}</td>
        <td class="mono">${dur}</td>
        <td style="color: var(--text-muted); font-size: 11px;">${dateStr}</td>
        <td>
          <button class="btn btn-sm" onclick="window.termboxApp.inspectRun('${run.run_id}')">Inspect</button>
          <button class="btn btn-sm btn-primary" onclick="window.termboxApp.replayRun('${run.run_id}')">Replay</button>
        </td>
      </tr>
    `;
  }).join('');
}

export function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// Attach to window for DOM onclick handlers
window.termboxApp = {
  checkHealth,
  fetchRuns,
  inspectRun: async (runId) => {
    try {
      const [run, lineage, artifactsData] = await Promise.all([
        TermboxAPI.getRun(runId),
        TermboxAPI.getLineage(runId).catch(() => []),
        TermboxAPI.listArtifacts(runId).catch(() => ({ artifacts: [] })),
      ]);
      const title = document.getElementById('modal-run-title');
      const content = document.getElementById('modal-run-content');
      const replayBtn = document.getElementById('btn-modal-replay');
      if (title) title.innerHTML = `Run Inspection: <span class="mono">${run.run_id}</span>`;
      if (replayBtn) replayBtn.onclick = () => window.termboxApp.replayRun(run.run_id);
      if (content) {
        content.innerHTML = `
          <div style="margin-bottom: 14px;">
            <span class="badge badge-${run.failure_mode || run.status}">${run.failure_mode || run.status}</span>
            <span class="mono" style="margin-left: 10px; color: var(--text-muted); font-size: 12px;">Exit: ${run.exit_code} | Duration: ${run.duration_ms}ms</span>
          </div>
          <div style="margin-bottom: 14px;">
            <div style="font-size: 12px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px;">Lineage History</div>
            <div id="modal-lineage-container"></div>
          </div>
          <div style="margin-bottom: 14px;">
            <div style="font-size: 12px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px;">Extracted Artifacts</div>
            <div id="modal-artifacts-container"></div>
          </div>
          <div class="terminal-box" id="modal-terminal-box">${ansiToHtml(run.combined_stdout) || '(no stdout)'}</div>
        `;
        renderLineageGraph(lineage, run.run_id, document.getElementById('modal-lineage-container'));
        renderArtifactsViewer(artifactsData.artifacts, run.run_id, document.getElementById('modal-artifacts-container'));
      }
      const modal = document.getElementById('run-detail-modal');
      if (modal) modal.style.display = 'flex';
    } catch (e) {
      alert('Failed to load run details: ' + e);
    }
  },
  replayRun: async (runId) => {
    try {
      const res = await TermboxAPI.replayRun(runId, {});
      await fetchRuns();
      window.termboxApp.inspectRun(res.run_id);
    } catch (e) {
      alert('Replay failed: ' + e);
    }
  },
  launchTemplate: async (templateId) => {
    try {
      const res = await TermboxAPI.launchTemplate(templateId);
      await fetchRuns();
      window.termboxApp.inspectRun(res.run_id);
    } catch (e) {
      alert('Failed to launch template: ' + e);
    }
  },
  openDiff: (runA, runB) => {
    const container = document.getElementById('diff-modal-content');
    if (container) openDiffModal(runA, runB, container);
    const modal = document.getElementById('diff-modal');
    if (modal) modal.style.display = 'flex';
  },
  openBatchModal: () => {
    const container = document.getElementById('batch-modal-content');
    if (container) openBatchRunner(container);
    const modal = document.getElementById('batch-modal');
    if (modal) modal.style.display = 'flex';
  },
  submitBatchFromUI: async () => {
    const name = document.getElementById('batch-name').value || 'batch_eval';
    const limit = parseInt(document.getElementById('batch-concurrency').value || '4', 10);
    const rawCmds = document.getElementById('batch-commands').value || '';
    const commands = rawCmds.split('\n').map(c => c.trim()).filter(c => c.length > 0);
    if (!commands.length) return alert('Please enter at least one command.');

    const resArea = document.getElementById('batch-results-area');
    if (resArea) resArea.innerHTML = '<div style="color: #60a5fa;">Running batch tasks...</div>';

    try {
      const res = await fetch('/batches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          parallel_limit: limit,
          tasks: commands.map(c => ({ main_cmd: c })),
        }),
      });
      const data = await res.json();
      if (resArea) {
        resArea.innerHTML = `
          <div style="background: var(--code-bg); padding: 12px; border-radius: 6px; border: 1px solid var(--card-border);">
            <div style="font-weight: bold; margin-bottom: 6px;">Batch Complete: ${data.name}</div>
            <div>Total: ${data.total_runs} | <span style="color:#10b981;">Passed: ${data.passed_count}</span> | <span style="color:#ef4444;">Failed: ${data.failed_count}</span></div>
          </div>
        `;
      }
      await fetchRuns();
    } catch (e) {
      alert('Batch launch failed: ' + e);
    }
  },
    const container = document.getElementById('templates-modal-content');
    if (container) openTemplatesDrawer(container);
    const modal = document.getElementById('templates-modal');
    if (modal) modal.style.display = 'flex';
  },
};

document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  fetchRuns();
  setInterval(fetchRuns, 8000);
});
