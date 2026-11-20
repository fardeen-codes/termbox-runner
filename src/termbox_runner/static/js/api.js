/**
 * Termbox Runner API client
 */
export const TermboxAPI = {
  async getHealth() {
    const res = await fetch('/health');
    return res.json();
  },

  async listRuns(params = {}) {
    const query = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== '') query.append(k, v);
    }
    const res = await fetch(`/runs?${query.toString()}`);
    return res.json();
  },

  async getRun(runId) {
    const res = await fetch(`/runs/${runId}`);
    if (!res.ok) throw new Error(`Run ${runId} not found`);
    return res.json();
  },

  async submitRun(task) {
    const res = await fetch('/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(task),
    });
    return res.json();
  },

  async replayRun(runId, overrides = {}) {
    const res = await fetch(`/runs/${runId}/replay`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(overrides),
    });
    return res.json();
  },

  async cancelRun(runId) {
    const res = await fetch(`/runs/${runId}/cancel`, { method: 'POST' });
    return res.json();
  },

  async getLineage(runId) {
    const res = await fetch(`/runs/${runId}/lineage`);
    return res.json();
  },

  async getDiff(runA, runB) {
    const res = await fetch(`/runs/${runA}/diff/${runB}`);
    return res.json();
  },

  async getTemplates() {
    const res = await fetch('/templates');
    return res.json();
  },

  async launchTemplate(templateId) {
    const res = await fetch(`/templates/${templateId}/launch`, { method: 'POST' });
    return res.json();
  },

  async listArtifacts(runId) {
    const res = await fetch(`/runs/${runId}/artifacts`);
    return res.json();
  },
};
