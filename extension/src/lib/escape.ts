const ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}

/** Escape a string for safe interpolation into HTML text/attributes. */
export function escapeHtml(value: string): string {
  // `?? c` keeps the regex and map impossible to desync — an unmapped match falls through
  // to the original character instead of emitting "undefined".
  return value.replace(/[&<>"']/g, (c) => ESCAPES[c] ?? c)
}
