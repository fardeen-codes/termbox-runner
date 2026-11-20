/**
 * Lightweight ANSI escape code parser to HTML
 */
export function ansiToHtml(text) {
  if (!text) return '';

  const colorMap = {
    '30': '#4b5563', // black / gray
    '31': '#ef4444', // red
    '32': '#10b981', // green
    '33': '#f59e0b', // yellow
    '34': '#3b82f6', // blue
    '35': '#8b5cf6', // magenta
    '36': '#06b6d4', // cyan
    '37': '#f3f4f6', // white
    '90': '#6b7280', // bright black
    '91': '#f87171', // bright red
    '92': '#34d399', // bright green
    '93': '#fbbf24', // bright yellow
    '94': '#60a5fa', // bright blue
    '95': '#c084fc', // bright magenta
    '96': '#22d3ee', // bright cyan
    '97': '#ffffff', // bright white
  };

  // Escape HTML characters first
  let escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Replace ANSI codes
  return escaped.replace(/\x1b\[([0-9;]+)m/g, (match, codes) => {
    const parts = codes.split(';');
    let styles = [];
    for (const code of parts) {
      if (code === '0') return '</span>';
      if (code === '1') styles.push('font-weight: bold;');
      if (code === '2') styles.push('opacity: 0.75;');
      if (code === '4') styles.push('text-decoration: underline;');
      if (colorMap[code]) styles.push(`color: ${colorMap[code]};`);
    }
    return `<span style="${styles.join(' ')}">`;
  });
}
