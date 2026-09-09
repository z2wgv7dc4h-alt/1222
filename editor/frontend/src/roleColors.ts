// Matches the --color-role-* tokens defined in index.css's @theme block.
const ROLE_COLORS: Record<string, string> = {
  intro: 'var(--color-role-intro)',
  build: 'var(--color-role-build)',
  breakdown: 'var(--color-role-breakdown)',
  verse: 'var(--color-role-verse)',
  chorus: 'var(--color-role-chorus)',
  solo: 'var(--color-role-solo)',
  chill: 'var(--color-role-chill)',
  interlude: 'var(--color-role-interlude)',
  outro: 'var(--color-role-outro)',
}

export function roleColor(role: string): string {
  return ROLE_COLORS[role] ?? 'var(--color-text-faint)'
}
