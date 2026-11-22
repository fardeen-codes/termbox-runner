"""Embedded dark-mode engineering inspection dashboard for termbox-runner."""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Termbox Runner — Evaluation & Sandbox Harness</title>
  <style>
    :root {
      --bg: #090d16;
      --card-bg: #111827;
      --card-border: #1f2937;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --accent: #3b82f6;
      --accent-hover: #2563eb;
      --passed: #10b981;
      --failed: #ef4444;
      --warning: #f59e0b;
      --purple: #8b5cf6;
      --cyan: #06b6d4;
      --code-bg: #030712;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.5;
      padding: 24px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--card-border);
    }
    .header h1 {
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.5px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .badge-live {
      font-size: 11px;
      font-weight: 600;
      background: rgba(16, 185, 129, 0.15);
      color: var(--passed);
      border: 1px solid rgba(16, 185, 129, 0.3);
      padding: 2px 8px;
      border-radius: 9999px;
      text-transform: uppercase;
    }
    .top-actions {
      display: flex;
      gap: 12px;
      align-items: center;
    }
    .btn {
      background: var(--card-border);
      color: var(--text);
      border: 1px solid #374151;
      padding: 7px 14px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 500;
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .btn:hover { background: #374151; }
    .btn-primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
    }
    .btn-primary:hover { background: var(--accent-hover); }
    .btn-sm { padding: 4px 8px; font-size: 11px; }

    /* Quick presets grid */
    .presets-box {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 24px;
    }
    .presets-box h3 {
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
      margin-bottom: 12px;
    }
    .preset-btns {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .btn-preset {
      background: #1f2937;
      border: 1px solid #374151;
      border-radius: 6px;
      padding: 8px 12px;
      color: #e5e7eb;
      font-size: 12px;
      cursor: pointer;
      text-align: left;
    }
    .btn-preset:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(96, 165, 250, 0.15);
      border-color: var(--accent);
      background: #283548;
    }
    .btn-preset strong { display: block; font-size: 13px; margin-bottom: 2px; }

    /* Stats bar */
    .stats-bar {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .stat-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 14px 18px;
    }
    .stat-title {
      font-size: 12px;
      color: var(--text-muted);
      margin-bottom: 6px;
      text-transform: uppercase;
    }
    .stat-val {
      font-size: 24px;
      font-weight: 700;
      color: #fff;
    }

    /* Filters */
    .filter-bar {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
      align-items: center;
      flex-wrap: wrap;
    }
    .filter-btn {
      background: transparent;
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      border-radius: 6px;
      padding: 5px 12px;
      font-size: 12px;
      cursor: pointer;
    }
    .filter-btn.active, .filter-btn:hover {
      background: #1f2937;
      color: #fff;
      border-color: #4b5563;
    }

    /* Table */
    .table-container {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 13px;
    }
    th {
      background: #172033;
      padding: 12px 16px;
      color: var(--text-muted);
      font-weight: 600;
      border-bottom: 1px solid var(--card-border);
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.5px;
    }
    td {
      padding: 12px 16px;
      border-bottom: 1px solid #1a2234;
      color: #e5e7eb;
    }
    tr:hover td { background: rgba(255, 255, 255, 0.02); }
    .mono { font-family: var(--font-mono); font-size: 12px; }

    /* Badges */
    .badge {
      display: inline-block;
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
    }
    .badge-PASSED { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-TIMEOUT { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-OOM_KILLED { background: rgba(139, 92, 246, 0.2); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.3); }
    .badge-ASSERTION_FAILED { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .badge-SETUP_ERROR { background: rgba(234, 88, 12, 0.2); color: #fb923c; border: 1px solid rgba(234, 88, 12, 0.3); }
    .badge-RUNTIME_ERROR { background: rgba(225, 29, 72, 0.2); color: #fb7185; border: 1px solid rgba(225, 29, 72, 0.3); }
    .badge-QUEUED { background: rgba(107, 114, 128, 0.2); color: #9ca3af; }
    .badge-RUNNING { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }

    /* Modal / Drawer */
    .modal-overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(4px);
      z-index: 100;
      justify-content: center;
      align-items: center;
      padding: 20px;
    }
    .modal-backdrop { backdrop-filter: blur(4px); }
    .modal {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      width: 100%;
      max-width: 850px;
      max-height: 90vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
    }
    .modal-header {
      padding: 16px 20px;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .modal-header h2 { font-size: 16px; font-weight: 600; }
    .modal-body {
      padding: 20px;
      overflow-y: auto;
      flex: 1;
    }
    .modal-footer {
      padding: 14px 20px;
      border-top: 1px solid var(--card-border);
      display: flex;
      justify-content: flex-end;
      gap: 10px;
    }
    .close-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 20px;
      cursor: pointer;
    }
    .close-btn:hover { color: #fff; }

    /* Terminal logs viewer */
    .terminal-box {
      background: var(--code-bg);
      border: 1px solid #1f2937;
      border-radius: 6px;
      padding: 14px;
      font-family: var(--font-mono);
      font-size: 12px;
      color: #e5e7eb;
      max-height: 280px;
      overflow-y: auto;
      white-space: pre-wrap;
      word-break: break-all;
      margin-top: 8px;
    }
    .form-group {
      margin-bottom: 14px;
    }
    .form-group label {
      display: block;
      font-size: 12px;
      font-weight: 500;
      color: var(--text-muted);
      margin-bottom: 4px;
    }
    .form-control {
      width: 100%;
      background: #030712;
      border: 1px solid #374151;
      border-radius: 6px;
      color: #fff;
      padding: 8px 10px;
      font-size: 13px;
      font-family: var(--font-mono);
    }
    .form-control:focus {
      outline: none;
      border-color: var(--accent);
    }
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .grid-3 {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 12px;
    }
    .detail-section {
      margin-bottom: 18px;
    }
    .detail-section h4 {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
      margin-bottom: 6px;
    }
    .steps-table {
      width: 100%;
      margin-top: 6px;
      font-size: 12px;
    }
    .steps-table td, .steps-table th {
      padding: 6px 10px;
    }
    .lineage-badge {
      font-size: 11px;
      background: rgba(59, 130, 246, 0.15);
      border: 1px solid rgba(59, 130, 246, 0.3);
      color: #60a5fa;
      padding: 2px 6px;
      border-radius: 4px;
      text-decoration: none;
    }
    .lineage-badge:hover { text-decoration: underline; }
  </style>
</head>
<body>

  <!-- Top Header -->
  <div class="header">
    <div>
      <h1>
        <span>📦 Termbox Runner</span>
        <span class="badge-live" id="daemon-status">Docker Online</span>
      </h1>
      <p style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
        Deterministic Sandboxed Task Runner & Evaluation Harness for Agents and Verifiers
      </p>
    </div>
    <div class="top-actions">
      <button class="btn" onclick="fetchRuns()">🔄 Refresh</button>
      <a href="/runs/export/csv" class="btn" style="text-decoration:none; display:inline-flex; align-items:center; gap:6px;">📊 Export CSV</a>
      <button class="btn btn-primary" onclick="openNewRunModal()">+ New Run</button>
    </div>
  </div>

  <!-- Quick Presets -->
  <div class="presets-box">
    <h3>⚡ Benchmark & Verification Presets</h3>
    <div class="preset-btns">
      <button class="btn-preset" onclick="submitPreset('pass')">
        <strong>✅ Clean Pass</strong>
        <span>Runs Python math calculation & exits 0</span>
      </button>
      <button class="btn-preset" onclick="submitPreset('assert')">
        <strong>❌ Test Assertion Failure</strong>
        <span>Executes pytest suite with failing assertion</span>
      </button>
      <button class="btn-preset" onclick="submitPreset('timeout')">
        <strong>⏳ Wall-clock Timeout</strong>
        <span>Hanging command with 2s strict limit</span>
      </button>
      <button class="btn-preset" onclick="submitPreset('oom')">
        <strong>💥 OOM Killed (SIGKILL 137)</strong>
        <span>Exceeds strict 32MB container memory cap</span>
      </button>
    </div>
  </div>

  <!-- Stats -->
  <div class="stats-bar">
    <div class="stat-card">
      <div class="stat-title">Total Executions</div>
      <div class="stat-val" id="stat-total">0</div>
    </div>
    <div class="stat-card">
      <div class="stat-title">Passed (Clean)</div>
      <div class="stat-val" style="color: var(--passed);" id="stat-passed">0</div>
    </div>
    <div class="stat-card">
      <div class="stat-title">Assertion Failures</div>
      <div class="stat-val" style="color: var(--failed);" id="stat-assert">0</div>
    </div>
    <div class="stat-card">
      <div class="stat-title">OOM / Timeouts</div>
      <div class="stat-val" style="color: var(--warning);" id="stat-oom-timeout">0</div>
    </div>
  </div>

  <!-- Filters -->
  <div class="filter-bar">
    <button class="filter-btn active" onclick="setFilter('')">All Runs</button>
    <button class="filter-btn" onclick="setFilter('PASSED')">Passed</button>
    <button class="filter-btn" onclick="setFilter('ASSERTION_FAILED')">Assertion Failed</button>
              <button class="filter-btn" onclick="setFilter('TIMEOUT')">Timeouts</button>
    <button class="filter-btn" onclick="setFilter('TIMEOUT')">Timeout</button>
    <button class="filter-btn" onclick="setFilter('OOM_KILLED')">OOM Killed</button>
    <button class="filter-btn" onclick="setFilter('SETUP_ERROR')">Setup Error</button>
    <button class="filter-btn" onclick="setFilter('RUNTIME_ERROR')">Runtime Error</button>
        <button class="filter-btn" onclick="setFilter('REPLAY')">Replays Only</button>
              <button class="filter-btn" onclick="setFilter('OOM_KILLED')">OOM Killed</button>
  </div>

  <!-- Runs Table -->
  <div class="table-container">
    <table>
      <thead>
        <tr>
          <th>Run ID</th>
          <th>Parent / Lineage</th>
          <th>Status</th>
          <th>Failure Mode</th>
          <th>Main Command</th>
          <th>Exit Code</th>
          <th style="cursor:pointer;">Duration ↕</th>
          <th>Executed At</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody id="runs-table-body">
        <tr>
          <td colspan="9" style="text-align: center; color: var(--text-muted); padding: 32px;">
            Loading execution manifests...
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- New Run Modal -->
  <div class="modal-overlay" id="new-run-modal">
    <div class="modal">
      <div class="modal-header">
        <h2>Submit Sandboxed Task Execution</h2>
        <button class="close-btn" onclick="closeModal('new-run-modal')">&times;</button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label>Docker Image</label>
          <input type="text" id="form-image" class="form-control" value="python:3.12-slim">
        </div>
        <div class="form-group">
          <label>Setup Command (Optional)</label>
          <input type="text" id="form-setup-cmd" class="form-control" placeholder="e.g. pip install -q pytest">
        </div>
        <div class="form-group">
          <label>Main Task / Agent Command</label>
          <input type="text" id="form-main-cmd" class="form-control" value="python -c &quot;print('Task execution succeeded')&quot;">
        </div>
        <div class="form-group">
          <label>Verifier / Evaluation Command (Optional)</label>
          <input type="text" id="form-verifier-cmd" class="form-control" placeholder="e.g. pytest tests/">
        </div>
        <div class="grid-3">
          <div class="form-group">
            <label>Memory Cap</label>
            <input type="text" id="form-mem-limit" class="form-control" value="512m">
          </div>
          <div class="form-group">
            <label>Timeout (seconds)</label>
            <input type="number" id="form-timeout" class="form-control" value="30">
          </div>
          <div class="form-group">
            <label>CPU Cores Quota</label>
            <input type="number" step="0.1" id="form-cpus" class="form-control" value="1.0">
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn" onclick="closeModal('new-run-modal')">Cancel</button>
        <button class="btn btn-primary" onclick="submitCustomRun()">🚀 Execute Sandbox Task</button>
      </div>
    </div>
  </div>

  <!-- Run Detail Modal -->
  <div class="modal-overlay" id="run-detail-modal">
    <div class="modal">
      <div class="modal-header">
        <h2 id="modal-run-title">Run Inspection</h2>
        <button class="close-btn" onclick="closeModal('run-detail-modal')">&times;</button>
      </div>
      <div class="modal-body" id="modal-run-content">
        <!-- Injected dynamically -->
      </div>
      <div class="modal-footer">
        <button class="btn btn-primary" id="btn-modal-replay">🔁 Replay Run</button>
        <a id="btn-download-stdout" class="btn btn-sm" target="_blank" style="text-decoration:none; margin-left:8px;">⬇ Download Logs</a>
        <a id="btn-download-junit" class="btn btn-sm" target="_blank" style="text-decoration:none; margin-left:8px;">JUnit XML</a>
        <button class="btn" onclick="closeModal('run-detail-modal')">Close</button>
      </div>
    </div>
  </div>

  <script>
    let currentFilter = '';
    let cachedRuns = [];

    async function checkHealth() {
      try {
        const res = await fetch('/health');
        const data = await res.json();
        const badge = document.getElementById('daemon-status');
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

    async function fetchRuns() {
      try {
        let url = '/runs?limit=100';
        if (currentFilter) url += `&failure_mode=${currentFilter}`;
        const res = await fetch(url);
        const data = await res.json();
        cachedRuns = data.runs || [];
        renderRuns(cachedRuns);
        updateStats();
      } catch (e) {
        console.error('Failed to fetch runs', e);
      }
    }

    function setFilter(mode) {
      currentFilter = mode;
      document.querySelectorAll('.filter-btn').forEach(btn => {
        if ((!mode && btn.textContent === 'All Runs') || btn.textContent.toUpperCase().includes(mode)) {
          btn.classList.add('active');
        } else {
          btn.classList.remove('active');
        }
      });
      fetchRuns();
    }

    function updateStats() {
      document.getElementById('stat-total').textContent = cachedRuns.length;
      document.getElementById('stat-passed').textContent = cachedRuns.filter(r => r.failure_mode === 'PASSED').length;
      document.getElementById('stat-assert').textContent = cachedRuns.filter(r => r.failure_mode === 'ASSERTION_FAILED').length;
      document.getElementById('stat-oom-timeout').textContent = cachedRuns.filter(r => r.failure_mode === 'OOM_KILLED' || r.failure_mode === 'TIMEOUT').length;
    }

    function renderRuns(runs) {
      const tbody = document.getElementById('runs-table-body');
      if (!runs.length) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 32px;">⚡ No execution manifests found. Choose a benchmark preset above or click + New Run to start!</td></tr>`;
        return;
      }
      tbody.innerHTML = runs.map(run => {
        const modeBadge = run.failure_mode ? `<span class="badge badge-${run.failure_mode}">${run.failure_mode}</span>` : `<span class="badge badge-${run.status}">${run.status}</span>`;
        const lineageHtml = run.parent_run_id 
          ? `<a href="javascript:inspectRun('${run.parent_run_id}')" class="lineage-badge">Replay of ${run.parent_run_id.slice(-6)}</a>` 
          : `<span style="color: #6b7280; font-size: 11px;">root (${run.replay_count} replays)</span>`;
        const dur = (run.duration_ms / 1000).toFixed(2) + 's';
        const dateStr = new Date(run.created_at).toLocaleTimeString();
        const shortCmd = run.main_cmd.length > 32 ? run.main_cmd.slice(0, 30) + '...' : run.main_cmd;

        return `
          <tr>
            <td class="mono"><strong><a href="javascript:inspectRun('${run.run_id}')" style="color: #60a5fa; text-decoration: none;">${run.run_id}</a></strong></td>
            <td>${lineageHtml}</td>
            <td><span class="badge badge-${run.status}">${run.status}</span></td>
            <td>${modeBadge}</td>
            <td class="mono" title="${run.main_cmd}">${shortCmd}</td>
            <td class="mono">${run.exit_code !== null ? run.exit_code : '-'}</td>
            <td class="mono">${dur}</td>
            <td style="color: var(--text-muted); font-size: 11px;">${dateStr}</td>
            <td>
              <button class="btn btn-sm" onclick="inspectRun('${run.run_id}')">Inspect</button>
              <button class="btn btn-sm btn-primary" onclick="replayRun('${run.run_id}')">Replay</button>
            </td>
          </tr>
        `;
      }).join('');
    }

    async function inspectRun(runId) {
      try {
        const [runRes, lineageRes] = await Promise.all([
          fetch(`/runs/${runId}`),
          fetch(`/runs/${runId}/lineage`).catch(() => null)
        ]);
        const run = await runRes.json();
        const lineage = lineageRes ? await lineageRes.json() : [];

        document.getElementById('modal-run-title').innerHTML = `Run Inspection: <span class="mono">${run.run_id}</span>`;
        document.getElementById('btn-modal-replay').onclick = () => replayRun(run.run_id);

        let stepsHtml = '';
        if (run.steps && run.steps.length) {
          stepsHtml = `
            <table class="steps-table">
              <thead><tr><th>Step</th><th>Exit</th><th style="cursor:pointer;">Duration ↕</th><th>Command</th></tr></thead>
              <tbody>
                ${run.steps.map(s => `
                  <tr>
                    <td><span class="badge" style="background:#1f2937;">${s.step}</span></td>
                    <td class="mono">${s.exit_code !== null ? s.exit_code : '-'}</td>
                    <td class="mono">${s.duration_ms}ms</td>
                    <td class="mono" style="color:#9ca3af;">${s.command}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          `;
        }

        let lineageHtml = '';
        if (lineage && lineage.length > 1) {
          lineageHtml = `
            <div class="detail-section">
              <h4>Replay Lineage Tree</h4>
              <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:6px;">
                ${lineage.map(item => `
                  <span class="lineage-badge" style="${item.run_id === run.run_id ? 'border-color: #60a5fa; font-weight:bold;' : ''}" onclick="inspectRun('${item.run_id}')">
                    ${item.run_id === run.run_id ? '👉 ' : ''}${item.run_id.slice(-6)} (${item.failure_mode || item.status})
                  </span>
                `).join(' ➔ ')}
              </div>
            </div>
          `;
        }

        document.getElementById('modal-run-content').innerHTML = `
          <div class="detail-section">
            <div style="display: flex; gap: 12px; margin-bottom: 12px; align-items:center;">
              <span class="badge badge-${run.failure_mode || run.status}">${run.failure_mode || run.status}</span>
              <span class="mono" style="font-size:12px; color:var(--text-muted);">Exit: ${run.exit_code} | Duration: ${run.duration_ms}ms | Image: ${run.task.image || 'default'}</span>
            </div>
            ${run.failure_reason ? `<div style="background: rgba(239, 68, 68, 0.1); border-left: 3px solid #ef4444; padding: 8px 12px; font-size: 12px; margin-bottom: 12px;"><strong>Diagnostic:</strong> ${run.failure_reason}</div>` : ''}
          </div>

          ${lineageHtml}

          <div class="detail-section">
            <h4>Execution Steps</h4>
            ${stepsHtml || '<div style="color:var(--text-muted); font-size:12px;">No steps recorded</div>'}
          </div>

          <div class="detail-section">
            <h4>Standard Output (stdout)</h4>
            <div class="terminal-box">${escapeHtml(run.combined_stdout) || '<span style="color:#6b7280;">(no stdout output)</span>'}</div>
          </div>

          <div class="detail-section">
            <h4>Standard Error (stderr)</h4>
            <div class="terminal-box" style="color: #fca5a5;">${escapeHtml(run.combined_stderr) || '<span style="color:#6b7280;">(no stderr output)</span>'}</div>
          </div>
        `;

        document.getElementById('run-detail-modal').style.display = 'flex';
      } catch (e) {
        alert('Failed to load run details: ' + e);
      }
    }

    async function replayRun(runId) {
      try {
        const res = await fetch(`/runs/${runId}/replay`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        const data = await res.json();
        closeModal('run-detail-modal');
        await fetchRuns();
        inspectRun(data.run_id);
      } catch (e) {
        alert('Replay failed: ' + e);
      }
    }

    async function submitPreset(preset) {
      let payload = {};
      if (preset === 'pass') {
        payload = {
          main_cmd: "python -c 'import math; print(math.factorial(6))'",
          limits: { timeout_seconds: 10, mem_limit: "256m" }
        };
      } else if (preset === 'assert') {
        payload = {
          main_cmd: "python -c 'print(42)'",
          verifier_cmd: "python -c 'assert 10 == 20'",
          limits: { timeout_seconds: 10 }
        };
      } else if (preset === 'timeout') {
        payload = {
          main_cmd: "python -c 'import time; time.sleep(10)'",
          limits: { timeout_seconds: 2 }
        };
      } else if (preset === 'oom') {
        payload = {
          main_cmd: "python -c 'b = bytearray(120 * 1024 * 1024)'",
          limits: { mem_limit: "32m", timeout_seconds: 10 }
        };
      }

      try {
        const res = await fetch('/runs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const run = await res.json();
        await fetchRuns();
        inspectRun(run.run_id);
      } catch (e) {
        alert('Preset execution failed: ' + e);
      }
    }

    async function submitCustomRun() {
      const payload = {
        image: document.getElementById('form-image').value,
        setup_cmd: document.getElementById('form-setup-cmd').value || null,
        main_cmd: document.getElementById('form-main-cmd').value,
        verifier_cmd: document.getElementById('form-verifier-cmd').value || null,
        limits: {
          mem_limit: document.getElementById('form-mem-limit').value,
          timeout_seconds: parseFloat(document.getElementById('form-timeout').value),
          cpu_quota: parseFloat(document.getElementById('form-cpus').value)
        }
      };

      try {
        const res = await fetch('/runs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        closeModal('new-run-modal');
        await fetchRuns();
        inspectRun(data.run_id);
      } catch (e) {
        alert('Failed to execute task: ' + e);
      }
    }



    function showToast(msg) {
      const t = document.getElementById('toast');
      if (t) {
        t.textContent = msg;
        t.style.display = 'block';
        setTimeout(() => { t.style.display = 'none'; }, 2500);
      }
    }


    function copyCommand(cmd) {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(cmd);
        showToast('Command copied: ' + cmd);
      }
    }

    function copyRunId(id) {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(id);
        alert('Copied run ID to clipboard: ' + id);
      }
    }


    let autoRefreshActive = true;
    function toggleAutoRefresh() {
      autoRefreshActive = !autoRefreshActive;
      showToast(autoRefreshActive ? 'Auto-refresh resumed' : 'Auto-refresh paused');
    }

    function openNewRunModal() {
      document.getElementById('new-run-modal').style.display = 'flex';
    }

    function closeModal(id) {
      document.getElementById(id).style.display = 'none';
    }


    function formatDurationPrecise(ms) {
      if (ms < 1000) return ms.toFixed(0) + 'ms';
      return (ms / 1000).toFixed(2) + 's';
    }


    function getExitCodeBadge(code) {
      if (code === null || code === undefined) return '-';
      const color = code === 0 ? '#10b981' : '#ef4444';
      return `<span style="color:${color}; font-weight:600;">${code}</span>`;
    }


    function renderStepProgressBar(percent) {
      return `<div style="background:#334155; border-radius:4px; height:6px; width:100%;"><div style="background:#3b82f6; width:${percent}%; height:100%;"></div></div>`;
    }

    function escapeHtml(text) {
      if (!text) return '';
      return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }


    window.addEventListener('keydown', (e) => {
      if (e.key === '?' && !e.target.matches('input, textarea')) {
        alert('Keyboard Shortcuts:\n/ : Focus Search\nEsc : Close Modal\nr : Refresh Runs');
      }
    });


    window.addEventListener('keydown', (e) => {
      if (e.key === 'r' && !e.target.matches('input, textarea')) {
        fetchRuns();
      }
    });

    // Init
    checkHealth();
    fetchRuns();
    setInterval(fetchRuns, 8000);
  </script>
  <div id="toast" style="display:none; position:fixed; bottom:20px; right:20px; background:#1e293b; color:#fff; border:1px solid #3b82f6; padding:10px 18px; border-radius:6px; box-shadow:0 4px 12px rgba(0,0,0,0.5); z-index:9999;"></div>
</body>
</html>
"""
