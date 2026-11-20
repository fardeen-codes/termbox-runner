/**
 * Search and tag filtering controller with debounce
 */
export function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

export function extractUniqueTags(runs) {
  const tagSet = new Set();
  runs.forEach(r => {
    if (r.tags && Array.isArray(r.tags)) {
      r.tags.forEach(t => tagSet.add(t));
    }
  });
  return Array.from(tagSet);
}
