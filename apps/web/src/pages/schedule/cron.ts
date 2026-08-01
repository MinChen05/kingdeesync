/**
 * 中文自然语言 <-> Cron 表达式双向转换工具。
 *
 * Cron 格式：秒 分 时 日 月 周（6 位，Go robfig/cron/v3 格式）。
 * 周日 = 0 或 7。
 */

// ---------- 类型定义 ----------

/** 中文频率描述 */
export interface CronLabel {
  /** 中文描述，如 "每 5 分钟" */
  text: string;
  /** 对应 Cron 表达式 */
  cron: string;
}

// ---------- 常量 ----------

const DAY_NAMES = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'] as const;

/** 内置预设（按使用频率排序） */
const PRESETS: CronLabel[] = [
  { text: '每 5 分钟', cron: '0 */5 * * * *' },
  { text: '每 10 分钟', cron: '0 */10 * * * *' },
  { text: '每 30 分钟', cron: '0 */30 * * * *' },
  { text: '每小时', cron: '0 0 * * * *' },
  { text: '每天 00:00', cron: '0 0 0 * * *' },
  { text: '每天 06:00', cron: '0 0 6 * * *' },
  { text: '每天 08:00', cron: '0 0 8 * * *' },
  { text: '每天 12:00', cron: '0 0 12 * * *' },
  { text: '每周日 00:00', cron: '0 0 0 * * 0' },
  { text: '每周一 08:00', cron: '0 0 8 * * 1' },
  { text: '每周五 18:00', cron: '0 0 18 * * 5' },
  { text: '每周六 09:00', cron: '0 0 9 * * 6' },
];

/** 返回预设列表（只读） */
export const cronPresets = Object.freeze(PRESETS);

// ---------- 中文 -> Cron ----------

/**
 * 将中文自然语言转换为 Cron 表达式。
 * 支持: "每 N 分钟", "每小时", "每天 HH:MM", "每周X HH:MM"。
 */
export function chineseToCron(text: string): string | null {
  const t = text.trim();

  // "每 N 分钟"
  const everyMinutes = t.match(/^每\s*(\d+)\s*分钟$/);
  if (everyMinutes) {
    const n = parseInt(everyMinutes[1], 10);
    if (n > 0 && n <= 59 && n * 2 <= 60) {
      return `0 */${n} * * * *`;
    }
    return null;
  }

  // "每小时"
  if (t === '每小时') {
    return '0 0 * * * *';
  }

  // "每天 HH:MM" 或 "每天 HH时MM分"
  const daily = t.match(/^每天\s*(\d{1,2}):?(\d{0,2})$/);
  if (daily) {
    const h = parseInt(daily[1], 10);
    const m = daily[2] ? parseInt(daily[2], 10) : 0;
    if (h >= 0 && h <= 23 && m >= 0 && m <= 59) {
      return `0 ${m} ${h} * * *`;
    }
    return null;
  }

  // "每周X" 或 "每周X HH:MM"
  const weekly = t.match(/^每(周|星期)([日零一二三四五六七天])\s*(?:(\d{1,2}):?(\d{0,2}))?$/);
  if (weekly) {
    const dayChar = weekly[2];
    const dayMap: Record<string, number> = {
      日: 0, 零: 0, 一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6, 天: 0,
    };
    const d = dayMap[dayChar];
    const h = weekly[3] ? parseInt(weekly[3], 10) : 0;
    const m = weekly[4] ? parseInt(weekly[4], 10) : 0;
    if (d !== undefined && h >= 0 && h <= 23 && m >= 0 && m <= 59) {
      return `0 ${m} ${h} * * ${d}`;
    }
    return null;
  }

  return null;
}

// ---------- Cron -> 中文 ----------

/** 解析 day-of-week 字段为中文，如 "1-6" → "周一至周五"，"0" → "周日" */
function parseDow(dow: string): string | null {
  // 单值: 0 → 周日（必须严格匹配，避免 "1-6" 被 parseInt 解析为 1）
  const single = parseInt(dow, 10);
  if (!isNaN(single) && single >= 0 && single <= 7 && String(single) === dow) {
    return DAY_NAMES[single === 7 ? 0 : single];
  }

  // 范围: 1-6 → 周一至周五
  const range = dow.match(/^(\d)-(\d)$/);
  if (range) {
    const from = parseInt(range[1], 10);
    const to = parseInt(range[2], 10);
    if (!isNaN(from) && !isNaN(to) && from >= 0 && from <= 7 && to >= 0 && to <= 7 && from < to) {
      const f = from === 7 ? 0 : from;
      const t = to === 7 ? 0 : to;
      return `${DAY_NAMES[f]}至${DAY_NAMES[t]}`;
    }
  }

  // 逗号分隔: 1,3,5 → 周一、周三、周五
  const list = dow.split(',');
  if (list.length > 1 && list.every((d) => {
    const n = parseInt(d, 10);
    return !isNaN(n) && n >= 0 && n <= 7;
  })) {
    return list.map((d) => {
      const n = parseInt(d, 10);
      return DAY_NAMES[n === 7 ? 0 : n];
    }).join('、');
  }

  return null;
}

/**
 * 将 Cron 表达式解析为中文自然语言描述。
 * 返回 null 表示无法解析为常见模式，应回退到原始表达式。
 */
export function cronToChinese(cron: string): string | null {
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 6) return null;

  const [sec, min, hour, dom, month, dow] = parts;

  // 每 N 分钟模式: 0 */N * * * *
  const slashStar = '*' + '/';
  if (sec === '0' && min.startsWith(slashStar) && hour === '*' && dom === '*' && month === '*' && dow === '*') {
    const n = parseInt(min.slice(2), 10);
    if (n > 0 && n <= 59) {
      return `每 ${n} 分钟`;
    }
  }

  // 每小时模式: 0 0 * * * *
  if (sec === '0' && min === '0' && hour === '*' && dom === '*' && month === '*' && dow === '*') {
    return '每小时';
  }

  // 每 N 小时模式: 0 0 */N * * * (dow = *)
  if (sec === '0' && min === '0' && hour.startsWith(slashStar) && dom === '*' && month === '*' && dow === '*') {
    const n = parseInt(hour.slice(2), 10);
    if (n > 0 && n <= 23) {
      return `每 ${n} 小时`;
    }
  }

  // 每天 HH:MM 模式 (dow = *)
  if (sec === '0' && dom === '*' && month === '*' && dow === '*') {
    const h = parseInt(hour, 10);
    const m = parseInt(min, 10);
    if (!isNaN(h) && !isNaN(m) && h >= 0 && h <= 23 && m >= 0 && m <= 59) {
      return `每天 ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    }
  }

  // "0 M H */N * D" -> 周X至周Y 每 N 小时 HH:MM
  if (sec === '0' && dom === '*' && month === '*' && dow !== '*') {
    const dowLabel = parseDow(dow);
    const h = parseInt(hour, 10);
    const m = parseInt(min, 10);

    // 每 N 小时 + 周范围: 0 0 */2 * * 1-6
    if (hour.startsWith(slashStar)) {
      const n = parseInt(hour.slice(2), 10);
      if (!isNaN(n) && n > 0 && n <= 23 && dowLabel) {
        return `${dowLabel} 每 ${n} 小时`;
      }
    }

    // 固定时间 + 周范围/单值: 0 0 2 * * 0
    if (!isNaN(h) && !isNaN(m) && h >= 0 && h <= 23 && m >= 0 && m <= 59 && dowLabel) {
      return `每${dowLabel} ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    }
  }

  return null;
}

/**
 * 将 Cron 表达式转换为中文描述，无法解析时回退到原始表达式。
 */
export function formatCron(cron: string): string {
  return cronToChinese(cron) || cron;
}
