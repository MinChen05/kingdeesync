import {
  ArrowRightOutlined,
  CheckOutlined,
  CopyOutlined,
  DeleteOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { Button, Drawer, Input, Space, Tag, Tooltip } from 'antd';
import React, { useEffect, useRef, useState } from 'react';
import type { FormItem } from '../types';

interface FormConfigDrawerProps {
  visible: boolean;
  form: FormItem | null;
  onSubmit: (data: Partial<FormItem>) => void;
  onCancel: () => void;
  submitting: boolean;
}

const FieldKeysEditor: React.FC<{
  value: string;
  onChange: (value: string) => void;
}> = ({ value, onChange }) => {
  const [input, setInput] = useState('');
  const tags = Array.from(
    new Set(
      value
        ? value
            .split(',')
            .map((item) => item.trim())
            .filter(Boolean)
        : [],
    ),
  );

  const addTag = () => {
    const nextTag = input.trim();
    if (nextTag && !tags.includes(nextTag)) {
      onChange([...tags, nextTag].join(', '));
      setInput('');
    }
  };

  const removeTag = (index: number) => {
    const next = [...tags];
    next.splice(index, 1);
    onChange(next.join(', '));
  };

  return (
    <div className="field-keys-editor">
      <div className="field-tag-list">
        {tags.map((tag, index) => (
          <Tag
            key={tag}
            className="field-key-tag"
            closable
            onClose={() => removeTag(index)}
          >
            {tag}
          </Tag>
        ))}
        {tags.length === 0 && (
          <span className="field-empty-tip">尚未配置同步字段</span>
        )}
      </div>
      <div className="field-key-input-row">
        <Input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onPressEnter={addTag}
          placeholder="输入金蝶 API 字段名，按回车添加"
          aria-label="新增同步字段"
        />
        <Button
          icon={<PlusOutlined />}
          onClick={addTag}
          disabled={!input.trim()}
          aria-label="添加字段"
        />
      </div>
      <div className="field-helper-text">
        已配置 {tags.length} 个字段，字段名不可重复
      </div>
    </div>
  );
};

interface MappingRow {
  id: number;
  key: string;
  value: string;
}

const FieldMapEditor: React.FC<{
  value: Record<string, string> | undefined;
  onChange: (value: Record<string, string>) => void;
}> = ({ value, onChange }) => {
  const [rows, setRows] = useState<MappingRow[]>([]);
  const nextRowId = useRef(0);

  useEffect(() => {
    if (value && Object.keys(value).length > 0) {
      setRows((currentRows) =>
        Object.entries(value).map(([key, item], index) => ({
          id: currentRows[index]?.id ?? nextRowId.current++,
          key,
          value: item,
        })),
      );
    } else {
      setRows([]);
    }
  }, [value]);

  const emitChange = (next: MappingRow[]) => {
    const map: Record<string, string> = {};
    next.forEach((row) => {
      if (row.key) map[row.key] = row.value;
    });
    onChange(map);
  };

  const update = (index: number, field: 'key' | 'value', nextValue: string) => {
    const next = [...rows];
    next[index] = { ...next[index], [field]: nextValue };
    setRows(next);
    emitChange(next);
  };

  const remove = (index: number) => {
    const next = [...rows];
    next.splice(index, 1);
    setRows(next);
    emitChange(next);
  };

  return (
    <div className="field-map-editor">
      {rows.length > 0 && (
        <div className="field-map-heading" aria-hidden="true">
          <span>金蝶源字段</span>
          <span>数据库目标列</span>
          <span />
        </div>
      )}
      {rows.length === 0 ? (
        <div className="field-map-empty">
          暂无字段映射，添加后将金蝶字段名转换为数据库列名
        </div>
      ) : (
        <div className="field-map-list">
          {rows.map((row, index) => (
            <div className="field-map-row" key={row.id}>
              <Input
                value={row.key}
                onChange={(event) => update(index, 'key', event.target.value)}
                placeholder="例如 FBillNo"
                aria-label={`第 ${index + 1} 行源字段`}
              />
              <ArrowRightOutlined className="field-map-arrow" />
              <Input
                value={row.value}
                onChange={(event) => update(index, 'value', event.target.value)}
                placeholder="例如 bill_no"
                aria-label={`第 ${index + 1} 行目标列`}
              />
              <Tooltip title="删除映射">
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => remove(index)}
                  aria-label={`删除第 ${index + 1} 行映射`}
                />
              </Tooltip>
            </div>
          ))}
        </div>
      )}
      <Button
        type="dashed"
        block
        icon={<PlusOutlined />}
        onClick={() =>
          setRows([...rows, { id: nextRowId.current++, key: '', value: '' }])
        }
      >
        添加字段映射
      </Button>
    </div>
  );
};

const Section: React.FC<{
  title: string;
  description: string;
  children: React.ReactNode;
}> = ({ title, description, children }) => (
  <section className="form-config-section">
    <div className="form-config-section-heading">
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
    {children}
  </section>
);

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
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (visible && form) {
      setFormId(form.form_id || '');
      setFieldKeys(form.field_keys || '');
      setFilterString(form.filter_string || '');
      setFieldMap(form.field_map || {});
      setCopied(false);
    }
  }, [visible, form]);

  useEffect(
    () => () => {
      if (copyTimer.current) clearTimeout(copyTimer.current);
    },
    [],
  );

  const handleCopyFormId = async () => {
    try {
      await navigator.clipboard.writeText(formId);
      setCopied(true);
      if (copyTimer.current) clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <Drawer
      rootClassName="form-config-drawer"
      title={
        <div className="form-config-drawer-title">
          <strong>编辑表单配置</strong>
          <span title={form?.form_name}>{form?.form_name}</span>
        </div>
      }
      size={640}
      open={visible}
      onClose={onCancel}
      footer={
        <div className="form-config-drawer-footer">
          <span>保存后立即应用到后续同步任务</span>
          <Space>
            <Button onClick={onCancel}>取消</Button>
            <Button
              type="primary"
              loading={submitting}
              onClick={() =>
                onSubmit({
                  form_id: formId,
                  field_keys: fieldKeys,
                  filter_string: filterString,
                  field_map: fieldMap,
                })
              }
            >
              保存配置
            </Button>
          </Space>
        </div>
      }
    >
      <div className="form-config-content">
        <Section title="表单标识" description="金蝶数据接口使用的 FormID">
          <div className="form-id-input">
            <Input
              value={formId}
              onChange={(event) => setFormId(event.target.value)}
              placeholder="例如 SAL_SaleOrder"
              aria-label="金蝶表单 ID"
              variant="borderless"
            />
            <Tooltip title={copied ? '已复制' : '复制表单 ID'}>
              <Button
                type="text"
                icon={copied ? <CheckOutlined /> : <CopyOutlined />}
                className={copied ? 'is-copied' : undefined}
                onClick={handleCopyFormId}
                aria-label="复制表单 ID"
              />
            </Tooltip>
          </div>
        </Section>
        <Section title="同步字段" description="仅拉取此处配置的金蝶 API 字段">
          <div className="field-editor-surface">
            <FieldKeysEditor value={fieldKeys} onChange={setFieldKeys} />
          </div>
        </Section>
        <Section title="查询过滤" description="可选的金蝶查询过滤表达式">
          <Input.TextArea
            className="filter-expression-input"
            value={filterString}
            onChange={(event) => setFilterString(event.target.value)}
            placeholder="例如 FSaleOrgId = 171190"
            autoSize={{ minRows: 3, maxRows: 7 }}
          />
        </Section>
        <Section title="字段映射" description="将源字段名转换为目标数据库列名">
          <div className="field-editor-surface">
            <FieldMapEditor value={fieldMap} onChange={setFieldMap} />
          </div>
        </Section>
      </div>
    </Drawer>
  );
};

export default FormConfigDrawer;
