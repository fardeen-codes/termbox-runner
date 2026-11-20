/**
 * Interactive SVG/HTML tree graph for replay lineage
 */
export function renderLineageGraph(lineageRuns, currentRunId, container) {
  if (!container) return;
  if (!lineageRuns || lineageRuns.length <= 1) {
    container.innerHTML = '<span style="color: var(--text-muted); font-size: 12px;">Single standalone run (no replays)</span>';
    return;
  }

  let html = '<div class="lineage-tree-wrapper" style="display: flex; align-items: center; gap: 12px; overflow-x: auto; padding: 10px 0;">';

  lineageRuns.forEach((run, idx) => {
    const isCurrent = run.run_id === currentRunId;
    const badgeClass = `badge-${run.failure_mode || run.status}`;

    html += `
      <div class="lineage-node ${isCurrent ? 'active-node' : ''}" 
           onclick="window.termboxApp.inspectRun('${run.run_id}')"
           style="background: var(--code-bg); border: 1px solid ${isCurrent ? '#3b82f6' : 'var(--card-border)'}; border-radius: 8px; padding: 10px 14px; min-width: 150px; cursor: pointer; transition: all 0.15s ease;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <strong class="mono" style="font-size: 12px; color: ${isCurrent ? '#60a5fa' : '#e5e7eb'};">
            ${isCurrent ? '👉 ' : ''}${run.run_id.slice(-8)}
          </strong>
          <span class="badge ${badgeClass}" style="font-size: 10px;">${run.failure_mode || run.status}</span>
        </div>
        <div style="font-size: 11px; color: var(--text-muted);">
          <span>⏱️ ${Math.round(run.duration_ms)}ms</span>
          <span style="margin-left: 8px;">Exit: ${run.exit_code !== null ? run.exit_code : '-'}</span>
        </div>
      </div>
    `;

    if (idx < lineageRuns.length - 1) {
      html += `
        <div class="lineage-arrow" style="color: #4b5563; font-size: 16px; font-weight: bold;">
          ➔
        </div>
      `;
    }
  });

  html += '</div>';
  container.innerHTML = html;
}
