import { describe, it, expect } from 'vitest';
import { colors } from './tokens';

describe('theme tokens', () => {
  it('exports all expected keys', () => {
    expect(colors).toHaveProperty('primary');
    expect(colors).toHaveProperty('success');
    expect(colors).toHaveProperty('error');
    expect(colors).toHaveProperty('warning');
    expect(colors).toHaveProperty('unknown');
    expect(colors).toHaveProperty('text');
    expect(colors).toHaveProperty('muted');
    expect(colors).toHaveProperty('dim');
    expect(colors).toHaveProperty('surface');
  });

  it('each value is a CSS variable reference', () => {
    for (const value of Object.values(colors)) {
      expect(value).toMatch(/^var\(--tk-/);
    }
  });

  it('maps to correct variable names', () => {
    expect(colors.primary).toBe('var(--tk-primary)');
    expect(colors.success).toBe('var(--tk-success)');
    expect(colors.error).toBe('var(--tk-error)');
    expect(colors.warning).toBe('var(--tk-warning)');
    expect(colors.unknown).toBe('var(--tk-unknown)');
    expect(colors.text).toBe('var(--tk-text)');
    expect(colors.muted).toBe('var(--tk-muted)');
    expect(colors.dim).toBe('var(--tk-dim)');
    expect(colors.surface).toBe('var(--tk-surface)');
  });
});
