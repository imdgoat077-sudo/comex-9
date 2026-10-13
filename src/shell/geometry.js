// Interface coordinates -> window content coordinates for native views (CLAUDE.md §3.1): the macOS hiddenInset title
// bar puts native views 28px below the interface's own coordinates.
export const MACOS_TITLEBAR_OFFSET = 28;

/** A rectangle measured in the interface, as bounds for a native view (page, popup layer). */
export function toNativeRect(rect, { padX = 0, padBottom = 0 } = {}) {
  return {
    x: Math.round(rect.left - padX),
    y: Math.round(rect.top + MACOS_TITLEBAR_OFFSET),
    width: Math.round(rect.width + 2 * padX),
    height: Math.round(rect.height + padBottom),
  };
}

/** Theme tokens for native popups, read from the interface's CSS so both always match. */
export function popupTheme() {
  const css = getComputedStyle(document.documentElement);
  const v = (name, fallback) => css.getPropertyValue(name).trim() || fallback;
  return {
    '--bg': v('--surface-1', '#1d2025'),
    '--fg': v('--text-1', '#ecedef'),
    '--fg2': v('--text-2', '#a2a7b0'),
    '--fg3': v('--text-3', '#6c717a'),
    '--line': v('--line', '#30343b'),
    '--hover': v('--surface-2', '#262a30'),
    '--sel': v('--surface-3', '#2f343b'),
    '--accent': v('--accent', '#7c9cff'),
    '--run': v('--status-run', '#e5b44a'),
    '--ok': v('--status-ok', '#4fb286'),
    '--err': v('--status-err', '#e5675c'),
  };
}
