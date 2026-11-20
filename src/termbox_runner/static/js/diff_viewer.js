import { TermboxAPI } from './api.js';

/**
 * Side-by-side run diff viewer component
 */
export async function openDiffModal(runA, runB, container) {
  if (!container) return;
  container.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 20px;">Computing unified run differential...</div>';

  try {
    const diff = await TermboxAPI.getDiff(runA, runB);
    const durSign = diff.duration_diff_ms > 0 ? `+${diff.duration_diff_ms}` : `${diff.duration_diff_ms}`;
    const memSign = diff.peak_memory_diff_bytes > 0 ? `+${Math.round(diff.peak_memory_diff_bytes / 1024)}` : `${Math.round(diff.peak_memory_diff_bytes / 1024)}`;

    let diffLinesHtml = '';
    const diffText = diff.stdout_unified_diff || '(Outputs are identical - no stdout diff)';
    diffText.split('\n').forEach(line => {
      let color = '#e5e7eb';
      let bg = 'transparent';
      if (line.startsWith('+') && !line.startsWith('+++')) {
        color = '#34d399';
        bg = 'rgba(16, 185, 129, 0.1)';
      } else if (line.startsWith('-') && !line.startsWith('---')) {
        color = '#f87171';
        bg = 'rgba(239, 68, 68, 0.1)';
      } else if (line.startsWith('@@')) {
        color = '#38bdf8';
      }
      diffLinesHtml += `<div style="color: ${color}; background: ${bg}; padding: 1px 4px;">${escapeHtml(line)}</div>`;
    });

    container.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 14px;">
        <div class="stat-card" style="padding: 10px;">
          <div class="stat-title">Status Delta</div>
          <div style="font-size: 13px; font-weight: bold; color: ${diff.status_changed ? '#f59e0b' : '#10b981'};">
            ${diff.status_changed ? 'STATUS CHANGED' : 'IDENTICAL'}
          </div>
        </div>
        <div class="stat-card" style="padding: 10px;">
          <div class="stat-title">Duration Delta</div>
          <div class="mono" style="font-size: 14px; font-weight: bold;">
            ${durSign} ms
          </div>
        </div>
        <div class="stat-card" style="padding: 10px;">
          <div class="stat-title">Peak Memory Delta</div>
          <div class="mono" style="font-size: 14px; font-weight: bold;">
            ${memSign} KB
          </div>
        </div>
      </div>
      <div style="font-size: 12px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 4px;">Unified Stdout Diff</div>
      <div class="terminal-box" style="max-height: 350px;">${diffLinesHtml}</div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="color: #ef4444;">Failed to compute run diff: ${err}</div>`;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
