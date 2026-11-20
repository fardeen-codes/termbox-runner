/**
 * Keyboard shortcuts for engineering workflow ergonomics
 */
export function initKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Ignore keystrokes when typing inside text inputs/textareas
    const tag = e.target.tagName.toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') {
      if (e.key === 'Escape') {
        e.target.blur();
      }
      return;
    }

    if (e.key === 'r') {
      e.preventDefault();
      window.termboxApp.fetchRuns();
    } else if (e.key === 'n') {
      e.preventDefault();
      const modal = document.getElementById('new-run-modal');
      if (modal) modal.style.display = 'flex';
    } else if (e.key === 't') {
      e.preventDefault();
      window.termboxApp.openTemplates();
    } else if (e.key === 'b') {
      e.preventDefault();
      window.termboxApp.openBatchModal();
    } else if (e.key === '/') {
      e.preventDefault();
      const searchBox = document.getElementById('run-search-input');
      if (searchBox) searchBox.focus();
    } else if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay').forEach(m => (m.style.display = 'none'));
    } else if (e.key === '?') {
      alert("⌨️ Termbox Runner Shortcuts:\n\n• r: Refresh runs\n• n: New run\n• t: Templates drawer\n• b: Batch matrix\n• /: Focus search\n• Esc: Close modals");
    }
  });
}
