/**
 * Visual SVG telemetry charts: phase duration breakdown and memory gauge
 */
export function renderTelemetryCharts(run, container) {
  if (!container || !run) return;

  const memMb = (run.peak_memory_bytes / (1024 * 1024)).toFixed(1);
  const steps = run.steps || [];
  const maxStepDur = Math.max(...steps.map(s => s.duration_ms), 1);

  let stepsBars = '';
  steps.forEach(s => {
    const pct = Math.min(100, Math.max(8, (s.duration_ms / maxStepDur) * 100));
    stepsBars += `
      <div style="margin-bottom: 6px;">
        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 2px;">
          <span class="mono">${s.step}</span>
          <span class="mono" style="color: var(--text-muted);">${s.duration_ms}ms</span>
        </div>
        <div style="background: #1f2937; border-radius: 4px; height: 8px; overflow: hidden;">
          <div style="background: #3b82f6; width: ${pct}%; height: 100%;"></div>
        </div>
      </div>
    `;
  });

  container.innerHTML = `
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; background: var(--code-bg); padding: 12px; border-radius: 8px; border: 1px solid var(--card-border);">
      <div>
        <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px;">Step Latency Breakdown</div>
        ${stepsBars || '<div style="font-size: 11px; color: var(--text-muted);">No step timings</div>'}
      </div>
      <div>
        <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px;">Resource Consumption</div>
        <div style="margin-bottom: 8px;">
          <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 2px;">
            <span>Peak Memory</span>
            <span class="mono" style="font-weight: bold; color: #a78bfa;">${memMb} MB</span>
          </div>
        </div>
        <div>
          <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 2px;">
            <span>Avg CPU Load</span>
            <span class="mono" style="font-weight: bold; color: #38bdf8;">${run.average_cpu_percent}%</span>
          </div>
        </div>
      </div>
    </div>
  `;
}
