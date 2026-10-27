import {
  CheckOutlined,
  DatabaseOutlined,
  PlayCircleOutlined,
  RestOutlined,
  StopOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useSearchParams } from '@umijs/max';
import { Button, Checkbox, Radio, Tag } from 'antd';
import React, { useEffect, useMemo, useState } from 'react';
import Panel from '@/components/Panel';
import { FORM_CATEGORIES } from '@/constants/formCategories';
import type { V1Form } from '@/services/v1';
import type { SyncMode } from '../types';

const { Group: CheckboxGroup } = Checkbox;

const STORAGE_KEY = 'kingdee-sync-last-config';

const MODE_OPTIONS: {
  value: SyncMode;
  label: string;
  description: string;
  icon: React.ReactNode;
}[] = [
  {
    value: 'incremental',
    label: '增量同步',
    description: '仅拉取上次同步后的变更',
    icon: <ThunderboltOutlined />,
  },
  {
    value: 'full',
    label: '全量同步',
    description: '完整拉取并合并现有数据',
    icon: <DatabaseOutlined />,
  },
  {
    value: 'reset',
    label: '重置同步',
    description: '清空现有数据后重新拉取',
    icon: <RestOutlined />,
  },
];

interface SyncConfigPanelProps {
  forms: V1Form[];
  formsLoading: boolean;
  status: string;
  starting: boolean;
  stopping: boolean;
  onStart: (mode: SyncMode, selectedForms: string[]) => void;
  onStop: () => void;
}

const SyncConfigPanel: React.FC<SyncConfigPanelProps> = ({
  forms,
  formsLoading,
  status,
  starting,
  stopping,
  onStart,
  onStop,
}) => {
  const [searchParams] = useSearchParams();
  const [mode, setMode] = useState<SyncMode>('incremental');
  const [selectedForms, setSelectedForms] = useState<string[]>([]);

  const isRunning = status === 'running' || status === 'stopping';
  const controlsLocked = isRunning || starting;

  const categorizedForms = useMemo(() => {
    const result: {
      label: string;
      items: { name: string; enabled: boolean }[];
    }[] = [];
    const allKnownForms = new Set<string>();

    for (const cat of Object.values(FORM_CATEGORIES)) {
      const items = cat.forms.map((name) => {
        const form = forms.find((item) => item.form_name === name);
        if (form) allKnownForms.add(name);
        return { name, enabled: form?.enabled ?? true };
      });
      if (items.length > 0) {
        result.push({ label: cat.label, items });
      }
    }

    const others = forms
      .filter((form) => !allKnownForms.has(form.form_name))
      .map((form) => ({ name: form.form_name, enabled: form.enabled }));
    if (others.length > 0) {
      result.push({ label: '其他', items: others });
    }

    return result;
  }, [forms]);

  const allFormNames = useMemo(
    () => forms.map((form) => form.form_name),
    [forms],
  );
  const allSelected =
    allFormNames.length > 0 &&
    allFormNames.every((name) => selectedForms.includes(name));
  const partiallySelected = selectedForms.length > 0 && !allSelected;

  useEffect(() => {
    const urlForms = searchParams.get('forms');
    if (urlForms) {
      const list = urlForms
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean);
      if (list.length > 0) {
        setSelectedForms(list);
        return;
      }
    }
    try {
      const last = localStorage.getItem(STORAGE_KEY);
      if (last) {
        const config = JSON.parse(last);
        if (config.mode) setMode(config.mode);
        if (Array.isArray(config.forms)) setSelectedForms(config.forms);
      }
    } catch {}
  }, [searchParams]);

  const saveLastConfig = () => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ mode, forms: selectedForms }),
      );
    } catch {}
  };

  const handleStart = () => {
    saveLastConfig();
    onStart(mode, selectedForms);
  };

  return (
    <Panel
      title="同步配置"
      loading={formsLoading}
      extra={
        <span
          className={`sync-config-state${isRunning ? ' is-active' : ''}`}
          aria-live="polite"
        >
          <span className="sync-config-state-dot" />
          {isRunning ? '配置已锁定' : '等待配置'}
        </span>
      }
    >
      <div className="sync-config-content">
        <section
          className="sync-config-section"
          aria-labelledby="sync-mode-title"
        >
          <div className="sync-section-heading">
            <div>
              <span className="sync-section-eyebrow">01</span>
              <span id="sync-mode-title">同步模式</span>
            </div>
            <span>选择本次执行方式</span>
          </div>
          <Radio.Group
            value={mode}
            onChange={(event) => setMode(event.target.value)}
            disabled={controlsLocked}
            className="sync-mode-selector"
          >
            {MODE_OPTIONS.map((option) => (
              <Radio
                key={option.value}
                value={option.value}
                className={`sync-mode-option${mode === option.value ? ' is-selected' : ''}${option.value === 'reset' ? ' is-reset' : ''}`}
              >
                <span className="sync-mode-option-icon">{option.icon}</span>
                <span className="sync-mode-option-copy">
                  <strong>{option.label}</strong>
                  <small>{option.description}</small>
                </span>
                <span className="sync-mode-option-check">
                  <CheckOutlined />
                </span>
              </Radio>
            ))}
          </Radio.Group>
          {mode === 'reset' && (
            <div className="sync-reset-notice" role="alert">
              重置模式会清空所选范围的现有数据，请确认后再启动。
            </div>
          )}
        </section>

        <section
          className="sync-config-section"
          aria-labelledby="sync-forms-title"
        >
          <div className="sync-section-heading">
            <div>
              <span className="sync-section-eyebrow">02</span>
              <span id="sync-forms-title">同步范围</span>
            </div>
            <Checkbox
              checked={allSelected}
              indeterminate={partiallySelected}
              onChange={(event) =>
                setSelectedForms(event.target.checked ? allFormNames : [])
              }
              disabled={controlsLocked}
            >
              全选
            </Checkbox>
          </div>

          <div className="sync-form-categories">
            {categorizedForms.map((category) => {
              const categoryNames = category.items.map((item) => item.name);
              const enabledNames = category.items
                .filter((item) => item.enabled)
                .map((item) => item.name);
              const selectedCount = categoryNames.filter((name) =>
                selectedForms.includes(name),
              ).length;
              const categorySelected =
                enabledNames.length > 0 &&
                enabledNames.every((name) => selectedForms.includes(name));
              return (
                <div key={category.label} className="sync-form-category">
                  <div className="sync-form-category-header">
                    <Checkbox
                      checked={categorySelected}
                      indeterminate={selectedCount > 0 && !categorySelected}
                      disabled={controlsLocked || enabledNames.length === 0}
                      onChange={(event) => {
                        const kept = selectedForms.filter(
                          (name) => !categoryNames.includes(name),
                        );
                        setSelectedForms(
                          event.target.checked
                            ? [...kept, ...enabledNames]
                            : kept,
                        );
                      }}
                    >
                      {category.label}
                    </Checkbox>
                    <Tag bordered={false}>
                      {selectedCount}/{category.items.length}
                    </Tag>
                  </div>
                  <CheckboxGroup
                    value={selectedForms.filter((name) =>
                      categoryNames.includes(name),
                    )}
                    onChange={(values) => {
                      const kept = selectedForms.filter(
                        (name) => !categoryNames.includes(name),
                      );
                      setSelectedForms([...kept, ...(values as string[])]);
                    }}
                    disabled={controlsLocked}
                    className="sync-form-options"
                  >
                    {category.items.map((item) => (
                      <Checkbox
                        key={item.name}
                        value={item.name}
                        disabled={!item.enabled || controlsLocked}
                      >
                        <span>{item.name}</span>
                        {!item.enabled && <small>已停用</small>}
                      </Checkbox>
                    ))}
                  </CheckboxGroup>
                </div>
              );
            })}
          </div>
          <div className="sync-selection-summary" aria-live="polite">
            <span>
              {selectedForms.length > 0
                ? `已选择 ${selectedForms.length} 个表单`
                : '未指定表单'}
            </span>
            <span>
              {selectedForms.length > 0
                ? `共 ${allFormNames.length} 个可选`
                : '将同步全部已启用表单'}
            </span>
          </div>
        </section>

        <div className="sync-actions">
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            size="large"
            disabled={controlsLocked}
            loading={starting}
            onClick={handleStart}
          >
            {isRunning ? '同步执行中' : '启动同步'}
          </Button>
          <Button
            danger
            icon={<StopOutlined />}
            size="large"
            disabled={!isRunning || stopping}
            loading={stopping}
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
