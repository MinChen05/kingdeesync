import { describe, expect, it } from 'vitest';
import { chineseToCron, cronToChinese, formatCron, cronPresets } from './cron';

describe('chineseToCron', () => {
  it('每 N 分钟', () => {
    expect(chineseToCron('每 5 分钟')).toBe('0 */5 * * * *');
    expect(chineseToCron('每10分钟')).toBe('0 */10 * * * *');
    expect(chineseToCron('每 30 分钟')).toBe('0 */30 * * * *');
  });

  it('每小时', () => {
    expect(chineseToCron('每小时')).toBe('0 0 * * * *');
  });

  it('每天 HH:MM', () => {
    expect(chineseToCron('每天 00:00')).toBe('0 0 0 * * *');
    expect(chineseToCron('每天 08:00')).toBe('0 0 8 * * *');
    expect(chineseToCron('每天 14:30')).toBe('0 30 14 * * *');
    expect(chineseToCron('每天 8:0')).toBe('0 0 8 * * *');
  });

  it('每周X', () => {
    expect(chineseToCron('每周日')).toBe('0 0 0 * * 0');
    expect(chineseToCron('每周一 08:00')).toBe('0 0 8 * * 1');
    expect(chineseToCron('每周三09:00')).toBe('0 0 9 * * 3');
    expect(chineseToCron('每周五 18:00')).toBe('0 0 18 * * 5');
    expect(chineseToCron('每周六')).toBe('0 0 0 * * 6');
    expect(chineseToCron('每星期天')).toBe('0 0 0 * * 0');
  });

  it('非法输入返回 null', () => {
    expect(chineseToCron('每 0 分钟')).toBeNull();
    expect(chineseToCron('每天 25:00')).toBeNull();
    expect(chineseToCron('随机字符串')).toBeNull();
    expect(chineseToCron('')).toBeNull();
  });
});

describe('cronToChinese', () => {
  it('每 N 分钟', () => {
    expect(cronToChinese('0 */5 * * * *')).toBe('每 5 分钟');
    expect(cronToChinese('0 */10 * * * *')).toBe('每 10 分钟');
    expect(cronToChinese('0 */30 * * * *')).toBe('每 30 分钟');
  });

  it('每小时', () => {
    expect(cronToChinese('0 0 * * * *')).toBe('每小时');
  });

  it('每天 HH:MM', () => {
    expect(cronToChinese('0 0 0 * * *')).toBe('每天 00:00');
    expect(cronToChinese('0 0 8 * * *')).toBe('每天 08:00');
    expect(cronToChinese('0 30 14 * * *')).toBe('每天 14:30');
  });

  it('每周X HH:MM', () => {
    expect(cronToChinese('0 0 0 * * 0')).toBe('每周日 00:00');
    expect(cronToChinese('0 0 8 * * 1')).toBe('每周一 08:00');
    expect(cronToChinese('0 0 18 * * 5')).toBe('每周五 18:00');
  });

  it('无法解析时返回 null', () => {
    expect(cronToChinese('0 0 1 1 * *')).toBeNull(); // 每月1号
    expect(cronToChinese('invalid')).toBeNull();
  });
});

describe('formatCron', () => {
  it('可解析的 cron 返回中文', () => {
    expect(formatCron('0 */5 * * * *')).toBe('每 5 分钟');
    expect(formatCron('0 0 8 * * 1')).toBe('每周一 08:00');
  });

  it('无法解析时回退原始表达式', () => {
    expect(formatCron('0 0 1 1 * *')).toBe('0 0 1 1 * *');
  });
});

describe('cronPresets', () => {
  it('预设列表可读且不为空', () => {
    expect(cronPresets.length).toBeGreaterThan(0);
    expect(cronPresets[0].text).toMatch(/每/);
  });
});
