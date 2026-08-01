/**
 * Theme token constants — mirror of CSS custom properties in theme.css.
 *
 * Use these values in inline `style={{ color: colors.error }}` instead of
 * raw hex strings.  When the theme changes, only `theme.css` + this file
 * need updating.
 */

export const colors = {
  primary:   'var(--tk-primary)',
  success:   'var(--tk-success)',
  error:     'var(--tk-error)',
  warning:   'var(--tk-warning)',
  unknown:   'var(--tk-unknown)',
  text:      'var(--tk-text)',
  textLight: 'var(--tk-text-light)',
  muted:     'var(--tk-muted)',
  dim:       'var(--tk-dim)',
  bright:    'var(--tk-bright)',
  bg:        'var(--tk-bg)',
  surface:   'var(--tk-surface)',
  indigo:    'var(--tk-indigo)',
} as const;

export type ThemeColor = typeof colors[keyof typeof colors];
