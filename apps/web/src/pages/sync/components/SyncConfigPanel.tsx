import {
  PlayCircleOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { App, Button, Checkbox, Radio, Tag, Typography } from 'antd';
import { useSearchParams } from '@umijs/max';
import React, { useEffect, useMemo, useState } from 'react';
import Panel from '@/components/Panel';
import type { V1Form } from '@/services/v1';
import type { SyncMode } from '../types';

const { Text } = Typography;
const { Group: CheckboxGroup } = Checkbox;

const STORAGE_KEY = 'kingdee-sync-last-config';

const FORM_CATEGORIES: Record<string, { label: string; forms: string[] }> = {
  procurement: { label: '采购', forms: ['采购订单', '采购入库单'] },
  sales: { label: '销售', forms: ['销售订单', '销售出库单', '销售退货单', '发货通知单'] },
  inventory: { label: '库存', forms: ['即时库存', '仓库'] },
  master: { label: '基础资料', forms: ['物料', '客户资料'] },
  production: { label: '生产', forms: ['生产订单主表', '生产订单明细', '生产入库单', '生产用料清单主表', '生产用料清单明细表'] },
  bom: { label: 'BOM', forms: ['物料清单', '物料清单子项'] },
  planning: { label: '计划', forms: ['预测订单', '委外订单'] },
  finance: { label: '财务', forms: ['科目余额表', '应付单', '应收单'] },
};

const MODE_DESC: Record<SyncMode, string> = {
  incremental: '仅同步自上次以来的变更数据',
  full: '全量拉取并合并数据',
  reset: '清空后全量拉取',
};

interface SyncConfigPanelProps {
  forms: V1Form[];
  formsLoading: boolean;
  status: string;
  onStart: (mode: SyncMode, selectedForms: string[]) => void;
  onStop: () => void;
}

/**
 * 同步配置面板：模式 + 表单选择 + 操作按钮。
 */
const SyncConfigPanel: React.FC<SyncConfigPanelProps> = ({
  forms,
  formsLoading,
  status,
  onStart,
  onStop,
}) => {
  const [searchParams] = useSearchParams();
  const [mode, setMode] = useState<SyncMode>('incremental');
  const [selectedForms, setSelectedForms] = useState<string[]>([]);

  const isRunning = status === 'running' || status === 'stopping';

  // 按业务分类组织表单
  const categorizedForms = useMemo(() => {
    const result: { label: string; items: { name: string; enabled: boolean }[] }[] = [];
    const allKnownForms = new Set<string>();

    for (const cat of Object.values(FORM_CATEGORIES)) {
      const items = cat.forms
        .map(name => {
          const f = forms.find(f => f.form_name === name);
          if (f) allKnownForms.add(name);
          return { name, enabled: f?.enabled ?? true };
        });
      if (items.length > 0) {
        result.push({ label: cat.label, items });
      }
    }

    const others = forms
      .filter(f => !allKnownForms.has(f.form_name))
      .map(f => ({ name: f.form_name, enabled: f.enabled }));
    if (others.length > 0) {
      result.push({ label: '其他', items: others });
    }

    return result;
  }, [forms]);

  const allFormNames = useMemo(() => forms.map(f => f.form_name), [forms]);

  // 加载配置
  useEffect(() => {
    const urlForms = searchParams.get('forms');
    if (urlForms) {
      const list = urlForms.split(',').map(s => s.trim()).filter(Boolean);
      if (list.length > 0) {
        setSelectedForms(list);
        return;
      }
    }
    try {
      const last = localStorage.getItem(STORAGE_KEY);
      if (last) {
        const cfg = JSON.parse(last);
        if (cfg.mode) setMode(cfg.mode);
        if (Array.isArray(cfg.forms)) setSelectedForms(cfg.forms);
      }
    } catch { /* ignore */ }
  }, [searchParams]);

  const saveLastConfig = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ mode, forms: selectedForms }));
    } catch { /* ignore */ }
  };

  const handleStart = () => {
    saveLastConfig();
    onStart(mode, selectedForms);
  };

  return (
    <Panel title="同步配置" loading={formsLoading}>
      <div className="space-y-5">
        {/* 同步模式 */}
        <div>
          <Text strong className="mb-2 block">同步模式</Text>
          <Radio.Group
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            buttonStyle="solid"
            disabled={isRunning}
            className="w-full"
          >
            <Radio.Button value="incremental">增量</Radio.Button>
            <Radio.Button value="full">全量</Radio.Button>
            <Radio.Button value="reset">重置</Radio.Button>
          </Radio.Group>
          <Text type="secondary" className="mt-1 block text-xs">
            {MODE_DESC[mode]}
          </Text>
        </div>

        {/* 表单选择 */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <Text strong>选择表单</Text>
            <Checkbox
              checked={selectedForms.length === allFormNames.length && allFormNames.length > 0}
              onChange={(e) => setSelectedForms(e.target.checked ? allFormNames : [])}
              disabled={isRunning}
            >
              全选 ({allFormNames.length})
            </Checkbox>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {categorizedForms.map((cat) => (
              <div key={cat.label} className="glass-card" style={{ padding: '10px 12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <Text strong style={{ fontSize: 12 }}>{cat.label}</Text>
                  <Tag style={{ fontSize: 10, padding: '0 6px' }}>
                    {cat.items.filter(i => selectedForms.includes(i.name)).length}/{cat.items.length}
                  </Tag>
                </div>
                <CheckboxGroup
                  value={selectedForms.filter(n => cat.items.some(i => i.name === n))}
                  onChange={(vals) => {
                    const catNames = cat.items.map(i => i.name);
                    const kept = selectedForms.filter(n => !catNames.includes(n));
                    setSelectedForms([...kept, ...(vals as string[])]);
                  }}
                  disabled={isRunning}
                  className="flex flex-col gap-0.5"
                >
                  {cat.items.map((item) => (
                    <Checkbox
                      key={item.name}
                      value={item.name}
                      disabled={!item.enabled || isRunning}
                      style={{ fontSize: 12, padding: '1px 0' }}
                    >
                      {item.name}
                    </Checkbox>
                  ))}
                </CheckboxGroup>
              </div>
            ))}
          </div>

          {selectedForms.length === 0 && (
            <Text type="secondary" className="mt-2 block text-xs">
              未选择表单时将同步所有已启用的表单
            </Text>
          )}
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-3">
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            size="large"
            disabled={isRunning}
            onClick={handleStart}
            className="flex-1"
          >
            {isRunning ? '同步中...' : '启动同步'}
          </Button>
          <Button
            danger
            icon={<StopOutlined />}
            size="large"
            disabled={!isRunning}
            onClick={onStop}
          >
            停止
          </Button>
        </div>
      </div>
    </Panel>
  );
};

export default SyncConfigPanel;
