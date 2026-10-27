import { Column } from '@ant-design/plots';
import { Empty } from 'antd';
import React, { useEffect, useMemo, useState } from 'react';
import Panel from '@/components/Panel';
import type { TrendDay } from '../hooks';

interface TrendChartProps {
  trend: TrendDay[];
  loading?: boolean;
}

function useCssVar(name: string, fallback: string): string {
  const [value, setValue] = useState(fallback);
  useEffect(() => {
    try {
      setValue(
        getComputedStyle(document.documentElement)
          .getPropertyValue(name)
          .trim() || fallback,
      );
    } catch {
      setValue(fallback);
    }
  }, [name, fallback]);
  return value;
}

const TrendChart: React.FC<TrendChartProps> = ({ trend, loading }) => {
  const primaryColor = useCssVar('--tk-primary', '#0f766e');
  const mutedColor = useCssVar('--tk-muted', '#64748b');
  const borderColor = useCssVar('--tk-border', '#e1e8e4');

  const data = useMemo(
    () => trend.map((item) => ({ ...item, day: item.date.slice(5) })),
    [trend],
  );

  const config = useMemo(
    () => ({
      data,
      xField: 'day',
      yField: 'sync_count',
      height: 270,
      autoFit: true,
      style: {
        fill: `l(270) 0:${primaryColor} 1:#5eead4`,
        radiusTopLeft: 7,
        radiusTopRight: 7,
      },
      axis: {
        x: {
          title: false,
          label: { style: { fill: mutedColor } },
          line: { style: { stroke: borderColor } },
        },
        y: {
          title: false,
          label: { style: { fill: mutedColor } },
          grid: {
            line: { style: { stroke: borderColor, lineDash: [4, 4] } },
          },
        },
      },
      tooltip: {
        title: (item: TrendDay & { day: string }) => item?.day,
        items: [
          { field: 'sync_count', name: '同步次数' },
          { field: 'records', name: '同步记录数' },
          {
            field: 'success_rate',
            name: '成功率',
            valueFormatter: (value: number) => `${Number(value).toFixed(1)}%`,
          },
        ],
      },
      interaction: { elementHighlight: { background: true } },
      animation: {
        appear: { animation: 'grow-in-y', duration: 500 },
      },
    }),
    [data, primaryColor, mutedColor, borderColor],
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
