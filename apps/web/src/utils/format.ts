const numberFormatter = new Intl.NumberFormat('en-US');

/**
 * Format a number with thousand separators.
 * Replaces numeral(val).format('0,0')
 */
export const formatNumber = (val: number | string): string => {
  const parsed = Number(val);
  return Number.isFinite(parsed) ? numberFormatter.format(parsed) : '';
};

/**
 * Format a number as yuan currency string.
 * Replaces `¥ ${numeral(val).format('0,0')}`
 */
export const formatYuan = (val: number | string) => `¥ ${formatNumber(val)}`;

/**
 * 统一时长格式化：各页面此前各有 6 份近似实现，收敛为一处。（原因：DRY + 全站显示一致）
 * - null/undefined/负数 → '-'
 * - < 60 秒 → 'N秒'
 * - < 1 小时 → 'N分N秒'
 * - ≥ 1 小时 → 'N时N分'
 */
export const formatDuration = (sec?: number | null): string => {
  if (sec == null || Number.isNaN(sec) || sec < 0) return '-';
  if (sec < 60) return `${Math.round(sec)}秒`;
  if (sec < 3600) {
    return `${Math.floor(sec / 60)}分${Math.round(sec % 60)}秒`;
  }
  return `${Math.floor(sec / 3600)}时${Math.floor((sec % 3600) / 60)}分`;
};
