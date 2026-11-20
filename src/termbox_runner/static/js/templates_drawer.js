import { TermboxAPI } from './api.js';

/**
 * Benchmark templates catalog drawer component
 */
export async function openTemplatesDrawer(container) {
  if (!container) return;
  container.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 20px;">Loading benchmark catalog...</div>';

  try {
    const templates = await TermboxAPI.getTemplates();
    let html = '<div class="templates-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px;">';

    templates.forEach(t => {
      html += `
        <div class="template-card" style="background: var(--code-bg); border: 1px solid var(--card-border); border-radius: 8px; padding: 14px; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 6px;">
              <strong style="font-size: 13px; color: #fff;">${t.name}</strong>
              <span class="badge" style="background: rgba(59, 130, 246, 0.2); color: #60a5fa; font-size: 10px;">${t.category}</span>
            </div>
            <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 10px;">${t.description}</p>
            <div class="mono" style="background: #030712; padding: 6px; border-radius: 4px; font-size: 11px; color: #9ca3af; margin-bottom: 12px;">
              ${t.task.main_cmd}
            </div>
          </div>
          <button class="btn btn-sm btn-primary" style="width: 100%; justify-content: center;" onclick="window.termboxApp.launchTemplate('${t.id}')">
            🚀 Launch Benchmark
          </button>
        </div>
      `;
    });

    html += '</div>';
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div style="color: #ef4444;">Failed to load templates: ${err}</div>`;
  }
}
