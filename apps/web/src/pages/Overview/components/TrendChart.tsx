import { Column } from '@ant-design/plots';
import { Empty } from 'antd';
import React, { useEffect, useMemo, useState } from 'react';
import type { TrendDay } from '../hooks';
import Panel from '@/components/Panel';

interface TrendChartProps {
  trend: TrendDay[];
  loading?: boolean;
}

/**
 * 从 CSS 变量中读取实际颜色值（Canvas 无法解析 var()）。
 */
function useCssVar(name: string, fallback: string): string {
  const [value, setValue] = useState(fallback);
  useEffect(() => {
    try {
      setValue(getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback);
    } catch {
      setValue(fallback);
    }
  }, [name, fallback]);
  return value;
}

/**
 * 近 7 天同步趋势：柱状图展示每日同步次数，tooltip 附带成功率。
 * 深色坐标轴适配整体主题。
 */
const TrendChart: React.FC<TrendChartProps> = ({ trend, loading }) => {
  const primaryColor = useCssVar('--tk-primary', '#38bdf8');
  const mutedColor = useCssVar('--tk-muted', '#94a3b8');

  const data = useMemo(
    () =>
      trend.map((d) => ({
        ...d,
        day: d.date.slice(5), // YYYY-MM-DD -> MM-DD
      })),
    [trend],
  );

  const config = useMemo(
    () => ({
      data,
      xField: 'day',
      yField: 'sync_count',
      height: 260,
      autoFit: true,
      style: {
        fill: `l(270) 0:${primaryColor} 1:rgba(56,189,248,0.25)`,
        radiusTopLeft: 6,
        radiusTopRight: 6,
      },
      axis: {
        x: {
          title: false,
          label: { style: { fill: mutedColor } },
          line: { style: { stroke: 'rgba(148,163,184,0.2)' } },
        },
        y: {
          title: false,
          label: { style: { fill: mutedColor } },
          grid: {
            line: {
              style: { stroke: 'rgba(148,163,184,0.08)', lineDash: [4, 4] },
            },
          },
        },
      },
      tooltip: {
        title: (d: TrendDay & { day: string }) => d?.day,
        items: [
          { field: 'sync_count', name: '同步次数' },
          { field: 'records', name: '同步记录数' },
          {
            field: 'success_rate',
            name: '成功率',
            valueFormatter: (v: number) => `${Number(v).toFixed(1)}%`,
          },
        ],
      },
      interaction: { elementHighlight: { background: true } },
    }),
    [data, primaryColor, mutedColor],
  );

  return (
    <Panel
      title="近 7 天同步趋势"
      loading={loading}
      bodyStyle={{ padding: '12px 16px 8px' }}
    >
      {data.length > 0 ? (
        <Column {...config} />
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无趋势数据"
        />
      )}
    </Panel>
  );
};

export default TrendChart;
