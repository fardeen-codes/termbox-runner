/**
 * Component to inspect and download extracted workspace artifacts
 */
export function renderArtifactsViewer(artifacts, runId, container) {
  if (!container) return;
  if (!artifacts || !artifacts.length) {
    container.innerHTML = '<span style="color: var(--text-muted); font-size: 12px;">No artifacts extracted for this run.</span>';
    return;
  }

  let html = '<div class="artifacts-list" style="display: flex; flex-direction: column; gap: 8px;">';

  artifacts.forEach(art => {
    const sizeKb = (art.size_bytes / 1024).toFixed(1);
    html += `
      <div class="artifact-row" style="display: flex; justify-content: space-between; align-items: center; background: var(--code-bg); border: 1px solid var(--card-border); padding: 8px 12px; border-radius: 6px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 14px;">📄</span>
          <span class="mono" style="font-size: 12px; color: #e5e7eb;">${art.path}</span>
          <span style="font-size: 11px; color: var(--text-muted);">(${sizeKb} KB)</span>
        </div>
        <div>
          <a href="/runs/${runId}/artifacts/${art.path}" target="_blank" download class="btn btn-sm btn-primary" style="text-decoration: none;">
            ⬇️ Download
          </a>
        </div>
      </div>
    `;
  });

  html += '</div>';
  container.innerHTML = html;
}
