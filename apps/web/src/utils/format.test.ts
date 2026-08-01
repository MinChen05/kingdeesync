import { describe, it, expect } from 'vitest';
import { formatDuration, formatNumber, formatYuan } from './format';

describe('formatNumber', () => {
  it('对普通数字添加千分位分隔符', () => {
    expect(formatNumber(1234)).toBe('1,234');
    expect(formatNumber(1234567)).toBe('1,234,567');
  });

  it('对字符串数字同样有效', () => {
    expect(formatNumber('1234')).toBe('1,234');
  });

  it('对 0 返回 0', () => {
    expect(formatNumber(0)).toBe('0');
  });

  it('对非数字值返回空字符串', () => {
    expect(formatNumber(NaN)).toBe('');
    expect(formatNumber(Infinity)).toBe('');
    expect(formatNumber(-Infinity)).toBe('');
  });
});

describe('formatYuan', () => {
  it('在数字前添加 ¥ 符号和千分位', () => {
    expect(formatYuan(1234)).toBe('¥ 1,234');
    expect(formatYuan(0)).toBe('¥ 0');
  });

  it('对字符串数字同样有效', () => {
    expect(formatYuan('9876')).toBe('¥ 9,876');
  });
});

describe('formatDuration', () => {
  it('对 null/undefined/NaN/负数返回 -', () => {
    expect(formatDuration(null)).toBe('-');
    expect(formatDuration(undefined)).toBe('-');
    expect(formatDuration(NaN)).toBe('-');
    expect(formatDuration(-1)).toBe('-');
    expect(formatDuration(-100)).toBe('-');
  });

  it('对 0 返回 0秒', () => {
    expect(formatDuration(0)).toBe('0秒');
  });

  it('对 < 60 秒返回 N秒', () => {
    expect(formatDuration(1)).toBe('1秒');
    expect(formatDuration(30)).toBe('30秒');
    expect(formatDuration(59)).toBe('59秒');
  });

  it('对秒数做四舍五入', () => {
    expect(formatDuration(30.4)).toBe('30秒');
    expect(formatDuration(30.5)).toBe('31秒');
  });

  it('对 60-3599 秒返回 N分N秒', () => {
    expect(formatDuration(60)).toBe('1分0秒');
    expect(formatDuration(90)).toBe('1分30秒');
    expect(formatDuration(125)).toBe('2分5秒');
    expect(formatDuration(3599)).toBe('59分59秒');
  });

  it('对 ≥ 3600 秒返回 N时N分', () => {
    expect(formatDuration(3600)).toBe('1时0分');
    expect(formatDuration(3660)).toBe('1时1分');
    expect(formatDuration(7200)).toBe('2时0分');
    expect(formatDuration(3661)).toBe('1时1分');
  });
});
