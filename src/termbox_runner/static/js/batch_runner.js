/**
 * Batch execution campaign runner component
 */
export function openBatchRunner(container) {
  if (!container) return;
  container.innerHTML = `
    <div style="display: flex; flex-direction: column; gap: 14px;">
      <div class="form-group">
        <label>Campaign Name</label>
        <input type="text" id="batch-name" class="form-control" value="Matrix Evaluation Run">
      </div>
      <div class="form-group">
        <label>Concurrency Limit</label>
        <input type="number" id="batch-concurrency" class="form-control" value="4" min="1" max="8">
      </div>
      <div class="form-group">
        <label>Tasks (One shell/python command per line)</label>
        <textarea id="batch-commands" class="form-control" rows="6" placeholder="python -c &quot;print('test 1')&quot;&#10;python -c &quot;print('test 2')&quot;&#10;pytest -v">python -c "print('Task A passed')"&#10;python -c "print('Task B passed')"&#10;python -c "assert 2 == 2"</textarea>
      </div>
      <button class="btn btn-primary" onclick="window.termboxApp.submitBatchFromUI()">
        🚀 Launch Batch Campaign
      </button>
      <div id="batch-results-area" style="margin-top: 10px;"></div>
    </div>
  `;
}
