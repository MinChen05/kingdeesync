import { describe, it, expect } from 'vitest';
import { parseForms } from './types';

describe('parseForms', () => {
  it('parses a valid JSON array string', () => {
    expect(parseForms('["A", "B"]')).toEqual(['A', 'B']);
  });

  it('returns empty array for empty string', () => {
    expect(parseForms('')).toEqual([]);
  });

  it('returns empty array for "[]"', () => {
    expect(parseForms('[]')).toEqual([]);
  });

  it('returns empty array for non-array JSON', () => {
    expect(parseForms('"single"')).toEqual([]);
    expect(parseForms('42')).toEqual([]);
    expect(parseForms('null')).toEqual([]);
  });

  it('returns empty array for invalid JSON', () => {
    expect(parseForms('{bad}')).toEqual([]);
    expect(parseForms('undefined')).toEqual([]);
  });
});
