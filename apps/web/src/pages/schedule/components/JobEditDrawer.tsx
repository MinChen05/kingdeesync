import {
  CalendarOutlined,
  CheckOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  InfoCircleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  App,
  Button,
  Checkbox,
  Drawer,
  Form,
  Input,
  Radio,
  Spin,
  Switch,
} from 'antd';
import React, { useEffect, useMemo, useState } from 'react';
import { FORM_CATEGORIES } from '@/constants/formCategories';
import { listForms } from '@/services/v1';
import { chineseToCron, cronPresets, formatCron } from '../cron';
import type { ScheduleJob, ScheduleJobSubmit } from '../types';
import { parseForms } from '../types';

interface JobEditDrawerProps {
  visible: boolean;
  job: ScheduleJob | null;
  allJobs: ScheduleJob[];
  onSubmit: (data: ScheduleJobSubmit) => void | Promise<void>;
  onCancel: () => void;
  submitting: boolean;
}

const { Group: CheckboxGroup } = Checkbox;

const JobEditDrawer: React.FC<JobEditDrawerProps> = ({
  visible,
  job,
  allJobs,
  onSubmit,
  onCancel,
  submitting,
}) => {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [cronText, setCronText] = useState('');
  const [selectedForms, setSelectedForms] = useState<string[]>([]);
  const syncType = Form.useWatch('sync_type', form);

  const formsReq = useQuery({
    queryKey: ['v1', 'forms'],
    queryFn: listForms,
    enabled: visible,
  });

  const categorizedForms = useMemo(() => {
    const allForms = formsReq.data ?? [];
    const result: {
      label: string;
      items: { name: string; enabled: boolean }[];
    }[] = [];
    const allKnown = new Set<string>();

    for (const category of Object.values(FORM_CATEGORIES)) {
      const items = category.forms.map((name) => {
        const formItem = allForms.find((item) => item.form_name === name);
        if (formItem) allKnown.add(name);
        return { name, enabled: formItem?.enabled ?? true };
      });
      if (items.length > 0) {
        result.push({ label: category.label, items });
      }
    }

    const others = allForms
      .filter((formItem) => !allKnown.has(formItem.form_name))
      .map((formItem) => ({
        name: formItem.form_name,
        enabled: formItem.enabled,
      }));
    if (others.length > 0) {
      result.push({ label: '其他', items: others });
    }

    return result;
  }, [formsReq.data]);

  const allFormNames = useMemo(
    () =>
      (formsReq.data ?? [])
        .map((formItem) => formItem.form_name)
        .sort((a, b) => a.localeCompare(b, 'zh-Hans')),
    [formsReq.data],
  );
  const allSelected =
    allFormNames.length > 0 &&
    allFormNames.every((name) => selectedForms.includes(name));

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

  const handleCategoryChange = (
    categoryNames: string[],
    values: React.ReactNode[],
  ) => {
    const kept = selectedForms.filter((name) => !categoryNames.includes(name));
    const nextSelected = [...kept, ...(values as string[])];
    setSelectedForms(nextSelected);
    form.setFieldsValue({ forms: nextSelected });
  };

  const handleSelectAll = (checked: boolean) => {
    const nextSelected = checked ? allFormNames : [];
    setSelectedForms(nextSelected);
    form.setFieldsValue({ forms: nextSelected });
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const cronExpr = chineseToCron(values.cron_text || cronText);
      if (!cronExpr) {
        message.warning('请输入有效的执行频率，如“每 5 分钟”或“每天 08:00”');
        return;
      }

      const currentName = job?.name;
      const duplicate = allJobs.find(
        (item) => item.name === values.name && item.name !== currentName,
      );
      if (duplicate) {
        message.error('任务名称已存在');
        return;
      }

      await onSubmit({
        name: values.name,
        cron_expr: cronExpr,
        sync_type: values.sync_type as 'incremental' | 'full',
        forms: values.forms || [],
        enabled: values.enabled,
      });
    } catch {}
  };

  return (
    <Drawer
      title={
        <div className="schedule-drawer-title">
          <strong>{job ? '编辑定时任务' : '新建定时任务'}</strong>
          <span>
            {job
              ? '调整执行计划与同步范围'
              : '配置一个可重复执行的自动同步计划'}
          </span>
        </div>
      }
      width={640}
      rootClassName="schedule-drawer-root"
      className="schedule-drawer"
      open={visible}
      onClose={onCancel}
      maskClosable={!submitting}
      closable={!submitting}
      styles={{ body: { padding: 0 } }}
      footer={
        <div className="schedule-drawer-footer">
          <span>
            {selectedForms.length > 0
              ? `已选择 ${selectedForms.length} 个表单`
              : '将同步全部已启用表单'}
          </span>
          <div>
            <Button onClick={onCancel} disabled={submitting}>
              取消
            </Button>
            <Button type="primary" loading={submitting} onClick={handleSubmit}>
              {job ? '保存修改' : '创建任务'}
            </Button>
          </div>
        </div>
      }
    >
      <Form
        form={form}
        layout="vertical"
        autoComplete="off"
        className="schedule-job-form"
      >
        <section className="schedule-form-section">
          <div className="schedule-form-section-heading">
            <span>01</span>
            <div>
              <strong>基本信息</strong>
              <small>为任务设置易识别的名称与同步方式</small>
            </div>
          </div>
          <Form.Item
            name="name"
            label="任务名称"
            rules={[{ required: true, message: '请输入任务名称' }]}
          >
            <Input placeholder="例如：每日业务数据全量同步" size="large" />
          </Form.Item>
          <Form.Item
            label="同步类型"
            name="sync_type"
            rules={[{ required: true, message: '请选择同步类型' }]}
            className="schedule-sync-type-field"
          >
            <Radio.Group className="schedule-sync-type-selector">
              <Radio
                value="incremental"
                className={syncType === 'incremental' ? 'is-selected' : ''}
              >
                <ThunderboltOutlined />
                <span>
                  <strong>增量同步</strong>
                  <small>仅处理上次后的数据变更</small>
                </span>
                <CheckOutlined className="schedule-type-check" />
              </Radio>
              <Radio
                value="full"
                className={syncType === 'full' ? 'is-selected' : ''}
              >
                <DatabaseOutlined />
                <span>
                  <strong>全量同步</strong>
                  <small>完整拉取并合并现有数据</small>
                </span>
                <CheckOutlined className="schedule-type-check" />
              </Radio>
            </Radio.Group>
          </Form.Item>
        </section>

        <section className="schedule-form-section">
          <div className="schedule-form-section-heading">
            <span>02</span>
            <div>
              <strong>执行频率</strong>
              <small>选择常用计划，或输入可识别的中文频率</small>
            </div>
          </div>
          <div className="schedule-cron-presets">
            {cronPresets.map((preset) => (
              <button
                key={preset.cron}
                type="button"
                className={cronText === preset.text ? 'is-selected' : ''}
                aria-pressed={cronText === preset.text}
                onClick={() => {
                  setCronText(preset.text);
                  form.setFieldsValue({ cron_text: preset.text });
                }}
              >
                <ClockCircleOutlined />
                {preset.text}
              </button>
            ))}
          </div>
          <Form.Item
            name="cron_text"
            label="自定义频率"
            rules={[{ required: true, message: '请输入执行频率' }]}
            extra={
              cronText ? (
                <span className="schedule-cron-preview">
                  <CalendarOutlined /> 当前计划：{cronText}
                </span>
              ) : (
                '支持“每 N 分钟”“每天 HH:MM”“每周X HH:MM”'
              )
            }
          >
            <Input
              placeholder="例如：每 30 分钟"
              size="large"
              onChange={(event) => setCronText(event.target.value)}
            />
          </Form.Item>
        </section>

        <section className="schedule-form-section">
          <div className="schedule-form-section-heading">
            <span>03</span>
            <div>
              <strong>同步范围</strong>
              <small>按业务分类选择需要自动同步的表单</small>
            </div>
          </div>
          <Form.Item name="forms" className="schedule-forms-field">
            <div className="schedule-drawer-forms">
              <div className="schedule-drawer-forms-toolbar">
                <span>
                  已选 <strong>{selectedForms.length}</strong> /{' '}
                  {allFormNames.length}
                </span>
                <Checkbox
                  checked={allSelected}
                  indeterminate={selectedForms.length > 0 && !allSelected}
                  onChange={(event) => handleSelectAll(event.target.checked)}
                >
                  全选表单
                </Checkbox>
              </div>
              <Spin spinning={formsReq.isPending}>
                <div className="schedule-drawer-category-grid">
                  {categorizedForms.map((category) => {
                    const categoryNames = category.items.map(
                      (item) => item.name,
                    );
                    const enabledNames = category.items
                      .filter((item) => item.enabled)
                      .map((item) => item.name);
                    const selectedCount = categoryNames.filter((name) =>
                      selectedForms.includes(name),
                    ).length;
                    const categorySelected =
                      enabledNames.length > 0 &&
                      enabledNames.every((name) =>
                        selectedForms.includes(name),
                      );
                    return (
                      <div
                        key={category.label}
                        className="schedule-drawer-category"
                      >
                        <div className="schedule-drawer-category-heading">
                          <Checkbox
                            checked={categorySelected}
                            indeterminate={
                              selectedCount > 0 && !categorySelected
                            }
                            disabled={enabledNames.length === 0}
                            onChange={(event) => {
                              const kept = selectedForms.filter(
                                (name) => !categoryNames.includes(name),
                              );
                              const nextSelected = event.target.checked
                                ? [...kept, ...enabledNames]
                                : kept;
                              setSelectedForms(nextSelected);
                              form.setFieldsValue({ forms: nextSelected });
                            }}
                          >
                            {category.label}
                          </Checkbox>
                          <span>
                            {selectedCount}/{categoryNames.length}
                          </span>
                        </div>
                        <CheckboxGroup
                          value={selectedForms.filter((name) =>
                            categoryNames.includes(name),
                          )}
                          onChange={(values) =>
                            handleCategoryChange(categoryNames, values)
                          }
                          className="schedule-drawer-category-options"
                        >
                          {category.items.map((item) => (
                            <Checkbox
                              key={item.name}
                              value={item.name}
                              disabled={!item.enabled}
                            >
                              {item.name}
                            </Checkbox>
                          ))}
                        </CheckboxGroup>
                      </div>
                    );
                  })}
                </div>
              </Spin>
              {selectedForms.length === 0 && (
                <div className="schedule-forms-notice">
                  <InfoCircleOutlined /> 未选择表单时，将同步全部已启用表单
                </div>
              )}
            </div>
          </Form.Item>
        </section>

        <section className="schedule-form-section schedule-form-status-section">
          <div>
            <strong>启用此任务</strong>
            <span>停用状态下仅保留配置，不会自动触发</span>
          </div>
          <Form.Item name="enabled" valuePropName="checked" noStyle>
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </section>
      </Form>
    </Drawer>
  );
};

export default JobEditDrawer;
