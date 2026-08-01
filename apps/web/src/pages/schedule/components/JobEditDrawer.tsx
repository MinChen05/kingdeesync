import { useQuery } from '@tanstack/react-query';
import {
  Button,
  Checkbox,
  Drawer,
  Form,
  Input,
  message,
  Radio,
  Switch,
} from 'antd';
import React, { useEffect, useMemo, useState } from 'react';
import { listForms } from '@/services/v1';
import type { V1Form } from '@/services/v1';
import type { ScheduleJob, ScheduleJobSubmit } from '../types';
import { parseForms } from '../types';
import { chineseToCron, cronPresets, formatCron } from '../cron';

interface JobEditDrawerProps {
  visible: boolean;
  job: ScheduleJob | null;
  allJobs: ScheduleJob[];
  onSubmit: (data: ScheduleJobSubmit) => void;
  onCancel: () => void;
  submitting: boolean;
}

const { Group: CheckboxGroup } = Checkbox;

/** 表单分类排序定义（原因：按业务模块分组，方便用户快速定位） */
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

/**
 * 任务编辑抽屉：创建/编辑定时任务
 */
const JobEditDrawer: React.FC<JobEditDrawerProps> = ({
  visible,
  job,
  allJobs,
  onSubmit,
  onCancel,
  submitting,
}) => {
  const [form] = Form.useForm();
  const [cronText, setCronText] = useState('');
  const [selectedForms, setSelectedForms] = useState<string[]>([]);

  const formsReq = useQuery({
    queryKey: ['v1', 'forms'],
    queryFn: listForms,
    enabled: visible,
  });

  // 按业务分类组织表单
  const categorizedForms = useMemo(() => {
    const allForms = formsReq.data ?? [];
    const result: { label: string; items: { name: string; enabled: boolean }[] }[] = [];
    const allKnown = new Set<string>();

    for (const cat of Object.values(FORM_CATEGORIES)) {
      const items = cat.forms
        .map(name => {
          const f = allForms.find(ff => ff.form_name === name);
          if (f) allKnown.add(name);
          return { name, enabled: f?.enabled ?? true };
        });
      if (items.length > 0) {
        result.push({ label: cat.label, items });
      }
    }

    const others = allForms
      .filter(f => !allKnown.has(f.form_name))
      .map(f => ({ name: f.form_name, enabled: f.enabled }));
    if (others.length > 0) {
      result.push({ label: '其他', items: others });
    }

    return result;
  }, [formsReq.data]);

  const allFormNames = useMemo(() => {
    return (formsReq.data ?? []).map(f => f.form_name).sort((a, b) => a.localeCompare(b, 'zh-Hans'));
  }, [formsReq.data]);

  // 填充表单
  useEffect(() => {
    if (visible) {
      if (job) {
        const jobForms = parseForms(job.forms);
        const label = formatCron(job.cron_expr);
        form.setFieldsValue({
          name: job.name,
          cron_text: label,
          sync_type: job.sync_type,
          forms: jobForms,
          enabled: job.enabled,
        });
        setCronText(label);
        setSelectedForms(jobForms);
      } else {
        form.resetFields();
        form.setFieldsValue({
          sync_type: 'incremental',
          enabled: true,
        });
        setCronText('');
        setSelectedForms([]);
      }
    }
  }, [visible, job, form]);

  // 分类卡片内 checkbox 变更时同步到 form
  const handleCategoryChange = (catNames: string[], vals: React.ReactNode[]) => {
    const kept = selectedForms.filter(n => !catNames.includes(n));
    const newSelected = [...kept, ...(vals as string[])];
    setSelectedForms(newSelected);
    form.setFieldsValue({ forms: newSelected });
  };

  // 全选
  const handleSelectAll = (checked: boolean) => {
    const newSelected = checked ? allFormNames : [];
    setSelectedForms(newSelected);
    form.setFieldsValue({ forms: newSelected });
  };

  // 提交
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const cronExpr = chineseToCron(values.cron_text || cronText);
      if (!cronExpr) {
        message.warning('请输入有效的执行频率，如"每 5 分钟"或"每天 08:00"');
        return;
      }

      const currentName = job?.name;
      const duplicate = allJobs.find(
        (j) => j.name === values.name && j.name !== currentName,
      );
      if (duplicate) {
        message.error('任务名称已存在');
        return;
      }

      onSubmit({
        name: values.name,
        cron_expr: cronExpr,
        sync_type: values.sync_type as 'incremental' | 'full',
        forms: values.forms || [],
        enabled: values.enabled,
      });
    } catch (_err) {
      // form validation failed
    }
  };

  return (
    <Drawer
      title={job ? '编辑任务' : '新建任务'}
      width={520}
      open={visible}
      onClose={onCancel}
      extra={
        <>
          <Button onClick={onCancel}>取消</Button>
          <Button type="primary" loading={submitting} onClick={handleSubmit}>
            {job ? '保存' : '创建'}
          </Button>
        </>
      }
    >
      <Form form={form} layout="vertical" autoComplete="off" style={{ gap: 24 }}>
        {/* 任务名称 */}
        <Form.Item
          name="name"
          label="任务名称"
          rules={[{ required: true, message: '请输入任务名称' }]}
        >
          <Input placeholder="例如：每日全量同步" />
        </Form.Item>

        {/* 同步类型 */}
        <Form.Item
          label="同步类型"
          name="sync_type"
          rules={[{ required: true, message: '请选择同步类型' }]}
        >
          <Radio.Group>
            <Radio.Button value="incremental">增量同步</Radio.Button>
            <Radio.Button value="full">全量同步</Radio.Button>
          </Radio.Group>
        </Form.Item>

        {/* 执行频率 */}
        <Form.Item label="执行频率">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {/* 预设频率卡片 */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {cronPresets.map((p) => (
                <button
                  key={p.cron}
                  type="button"
                  onClick={() => {
                    setCronText(p.text);
                    form.setFieldsValue({ cron_text: p.text });
                  }}
                  style={{
                    padding: '4px 10px',
                    borderRadius: 6,
                    border: cronText === p.text ? '1px solid #38bdf8' : '1px solid rgba(148,163,184,0.15)',
                    backgroundColor: cronText === p.text ? 'rgba(56,189,248,0.12)' : 'rgba(148,163,184,0.06)',
                    color: cronText === p.text ? '#38bdf8' : '#94a3b8',
                    fontSize: 12,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {p.text}
                </button>
              ))}
            </div>
            <Form.Item
              name="cron_text"
              noStyle
              rules={[{ required: true, message: '请输入执行频率' }]}
            >
              <Input
                placeholder={'或输入中文频率，如"每 30 分钟"'}
                onChange={(e) => setCronText(e.target.value)}
              />
            </Form.Item>
          </div>
        </Form.Item>

        {/* 关联表单 */}
        <Form.Item label="关联表单" name="forms">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {/* 全选 */}
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Checkbox
                checked={selectedForms.length === allFormNames.length && allFormNames.length > 0}
                onChange={(e) => handleSelectAll(e.target.checked)}
                style={{ fontSize: 12, color: 'var(--tk-dim)' }}
              >
                全选 ({allFormNames.length})
              </Checkbox>
            </div>
            {/* 分类表单卡片 */}
            <div className="grid grid-cols-2 gap-2">
              {categorizedForms.map((cat) => {
                const catNames = cat.items.map(i => i.name);
                return (
                  <div
                    key={cat.label}
                    className="glass-card"
                    style={{ padding: '8px 10px' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: '#cbd5e1' }}>
                        {cat.label}
                      </span>
                      <span style={{ fontSize: 11, color: 'var(--tk-dim)' }}>
                        {catNames.filter(n => selectedForms.includes(n)).length}/{catNames.length}
                      </span>
                    </div>
                    <CheckboxGroup
                      value={selectedForms.filter(n => catNames.includes(n))}
                      onChange={(vals) => handleCategoryChange(catNames, vals)}
                      className="flex flex-col gap-0.5"
                    >
                      {cat.items.map((item) => (
                        <Checkbox
                          key={item.name}
                          value={item.name}
                          disabled={!item.enabled}
                          style={{ fontSize: 12, padding: '0 0' }}
                        >
                          {item.name}
                        </Checkbox>
                      ))}
                    </CheckboxGroup>
                  </div>
                );
              })}
            </div>
            {selectedForms.length === 0 && (
              <div style={{ fontSize: 12, color: 'var(--tk-dim)' }}>
                未选择表单时将同步所有已启用的表单
              </div>
            )}
          </div>
        </Form.Item>

        {/* 启用状态 */}
        <Form.Item name="enabled" label="启用状态" valuePropName="checked">
          <Switch checkedChildren="启用" unCheckedChildren="禁用" />
        </Form.Item>
      </Form>
    </Drawer>
  );
};

export default JobEditDrawer;
