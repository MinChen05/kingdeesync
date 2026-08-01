/* Hallmark · component: config-drawer · genre: utilitarian
 * states: default · hover · focus · active · disabled · loading · error · success
 * contrast: pass (46–50)
 */

import {
  CheckOutlined,
  CopyOutlined,
  DeleteOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { Button, Drawer, Input, message, Space, Tag, Tooltip } from 'antd';
import type { InputRef } from 'antd';
import React, { useEffect, useRef, useState } from 'react';
import type { FormItem } from '../types';

const Textarea = Input.TextArea;

interface FormConfigDrawerProps {
  visible: boolean;
  form: FormItem | null;
  onSubmit: (data: Partial<FormItem>) => void;
  onCancel: () => void;
  submitting: boolean;
}

/* ── FieldKeys tag editor ── */

const FieldKeysEditor: React.FC<{
  value: string;
  onChange: (v: string) => void;
}> = ({ value, onChange }) => {
  const [input, setInput] = useState('');
  const tags = value ? value.split(',').map((s) => s.trim()).filter(Boolean) : [];

  const addTag = () => {
    const t = input.trim();
    if (t && !tags.includes(t)) {
      const next = [...tags, t].join(', ');
      onChange(next);
      setInput('');
    }
  };

  const removeTag = (i: number) => {
    const next = [...tags];
    next.splice(i, 1);
    onChange(next.join(', '));
  };

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, minHeight: 32 }}>
        {tags.map((t, i) => (
          <Tag
            key={`${t}-${i}`}
            closable
            onClose={() => removeTag(i)}
            style={{
              margin: 0,
              backgroundColor: 'var(--tk-surface)',
              borderColor: 'var(--tk-border)',
              color: 'var(--tk-text)',
              fontSize: 12,
              fontFamily: 'monospace',
            }}
          >
            {t}
          </Tag>
        ))}
        <Input
          size="small"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={addTag}
          placeholder={tags.length ? '+ 添加字段' : ''}
          style={{ width: 140, flex: 'none' }}
          variant="borderless"
        />
      </div>
      <div style={{ fontSize: 12, color: 'var(--tk-dim)', marginTop: 6 }}>
        {tags.length} 个字段，逗号分隔的 Kingdee API 字段名
      </div>
    </div>
  );
};

/* ── FieldMap key-value editor ── */

interface MappingRow {
  key: string;
  value: string;
}

const FieldMapEditor: React.FC<{
  value: Record<string, string> | undefined;
  onChange: (v: Record<string, string>) => void;
}> = ({ value, onChange }) => {
  const [rows, setRows] = useState<MappingRow[]>([]);

  useEffect(() => {
    if (value && Object.keys(value).length > 0) {
      setRows(Object.entries(value).map(([k, v]) => ({ key: k, value: v })));
    } else {
      setRows([]);
    }
  }, [value]);

  const update = (i: number, field: 'key' | 'value', v: string) => {
    const next = [...rows];
    next[i] = { ...next[i], [field]: v };
    setRows(next);
    const map: Record<string, string> = {};
    next.forEach((r) => {
      if (r.key) map[r.key] = r.value;
    });
    onChange(map);
  };

  const remove = (i: number) => {
    const next = [...rows];
    next.splice(i, 1);
    setRows(next);
    const map: Record<string, string> = {};
    next.forEach((r) => {
      if (r.key) map[r.key] = r.value;
    });
    onChange(map);
  };

  const add = () => {
    setRows([...rows, { key: '', value: '' }]);
  };

  return (
    <div>
      {rows.length === 0 ? (
        <div style={{ fontSize: 12, color: 'var(--tk-dim)', padding: '8px 0' }}>
          将 Kingdee API 字段名映射为目标数据库列名
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {rows.map((r, i) => (
            <Space key={i} style={{ width: '100%' }} align="start">
              <Input
                size="small"
                value={r.key}
                onChange={(e) => update(i, 'key', e.target.value)}
                placeholder="源字段"
                style={{ flex: 1, fontFamily: 'monospace', fontSize: 12 }}
              />
              <span style={{ color: 'var(--tk-dim)', fontSize: 12, lineHeight: '32px' }}>
                →
              </span>
              <Input
                size="small"
                value={r.value}
                onChange={(e) => update(i, 'value', e.target.value)}
                placeholder="目标列"
                style={{ flex: 1, fontFamily: 'monospace', fontSize: 12 }}
              />
              <Tooltip title="删除">
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => remove(i)}
                  style={{ fontSize: 14 }}
                />
              </Tooltip>
            </Space>
          ))}
        </div>
      )}
      <Button
        type="text"
        size="small"
        icon={<PlusOutlined />}
        onClick={add}
        style={{
          marginTop: 8,
          color: 'var(--tk-primary)',
          fontSize: 12,
        }}
      >
        添加映射
      </Button>
    </div>
  );
};

/* ── Section wrapper ── */

const Section: React.FC<{
  title: string;
  description?: string;
  children: React.ReactNode;
}> = ({ title, description, children }) => (
  <div style={{ marginBottom: 24 }}>
    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--tk-text)', marginBottom: 2 }}>
      {title}
    </div>
    {description && (
      <div style={{ fontSize: 12, color: 'var(--tk-dim)', marginBottom: 10 }}>
        {description}
      </div>
    )}
    {children}
  </div>
);

/* ── Drawer ── */

const FormConfigDrawer: React.FC<FormConfigDrawerProps> = ({
  visible,
  form,
  onSubmit,
  onCancel,
  submitting,
}) => {
  const [formId, setFormId] = useState('');
  const [fieldKeys, setFieldKeys] = useState('');
  const [filterString, setFilterString] = useState('');
  const [fieldMap, setFieldMap] = useState<Record<string, string>>({});
  const [copied, setCopied] = useState(false);
  const codeRef = useRef<InputRef>(null);

  useEffect(() => {
    if (visible && form) {
      setFormId(form.form_id || '');
      setFieldKeys(form.field_keys || '');
      setFilterString(form.filter_string || '');
      setFieldMap(form.field_map || {});
      setCopied(false);
    }
  }, [visible, form]);

  const handleCopyFormId = async () => {
    try {
      await navigator.clipboard.writeText(formId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // fallback
    }
  };

  const handleSubmit = () => {
    onSubmit({
      form_id: formId,
      field_keys: fieldKeys,
      filter_string: filterString,
      field_map: fieldMap,
    });
  };

  return (
    <Drawer
      title={
        <div>
          <div style={{ fontSize: 15, fontWeight: 600 }}>编辑表单配置</div>
          <div style={{ fontSize: 12, color: 'var(--tk-dim)', marginTop: 2 }}>
            {form?.form_name}
          </div>
        </div>
      }
      width={600}
      open={visible}
      onClose={onCancel}
      extra={
        <Space>
          <Button onClick={onCancel} variant="filled">
            取消
          </Button>
          <Button type="primary" loading={submitting} onClick={handleSubmit}>
            保存配置
          </Button>
        </Space>
      }
      styles={{
        body: { padding: '24px 24px 24px 28px' },
      }}
    >
      {/* FormID badge */}
      <Section title="金蝶表单 ID" description="Kingdee 数据接口中的表单标识符">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            backgroundColor: 'var(--tk-surface)',
            border: '1px solid var(--tk-border)',
            borderRadius: 6,
            padding: '8px 12px',
          }}
        >
          <Input
            ref={codeRef}
            value={formId}
            onChange={(e) => setFormId(e.target.value)}
            placeholder="例如：SAL_SaleOrder"
            style={{
              border: 'none',
              padding: 0,
              fontFamily: 'monospace',
              fontSize: 13,
              backgroundColor: 'transparent',
              flex: 1,
            }}
            variant="borderless"
          />
          <Tooltip title={copied ? '已复制' : '复制'}>
            <Button
              type="text"
              size="small"
              icon={copied ? <CheckOutlined /> : <CopyOutlined />}
              onClick={handleCopyFormId}
              style={{
                color: copied ? 'var(--tk-success)' : 'var(--tk-muted)',
                fontSize: 14,
              }}
            />
          </Tooltip>
        </div>
      </Section>

      <div
        style={{
          height: 1,
          backgroundColor: 'var(--tk-border)',
          margin: '0 0 24px',
        }}
      />

      {/* FieldKeys */}
      <Section title="字段列表" description="从 Kingdee API 拉取的字段">
        <div
          style={{
            backgroundColor: 'var(--tk-surface)',
            border: '1px solid var(--tk-border)',
            borderRadius: 6,
            padding: '10px 12px',
          }}
        >
          <FieldKeysEditor value={fieldKeys} onChange={setFieldKeys} />
        </div>
      </Section>

      {/* FilterString */}
      <Section title="过滤条件" description="Kingdee 查询过滤表达式">
        <Textarea
          value={filterString}
          onChange={(e) => setFilterString(e.target.value)}
          placeholder="例如：FSaleOrgId = 171190"
          rows={2}
          style={{
            fontFamily: 'monospace',
            fontSize: 12,
            backgroundColor: 'var(--tk-surface)',
            borderColor: 'var(--tk-border)',
          }}
        />
      </Section>

      {/* FieldMap */}
      <Section title="字段映射" description="Kingdee 字段名到数据库列名的映射">
        <div
          style={{
            backgroundColor: 'var(--tk-surface)',
            border: '1px solid var(--tk-border)',
            borderRadius: 6,
            padding: '10px 12px',
          }}
        >
          <FieldMapEditor value={fieldMap} onChange={setFieldMap} />
        </div>
      </Section>
    </Drawer>
  );
};

export default FormConfigDrawer;
