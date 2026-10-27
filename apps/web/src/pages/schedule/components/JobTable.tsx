import {
  CalendarOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseOutlined,
  DeleteOutlined,
  EditOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import {
  App,
  Button,
  Checkbox,
  Input,
  Popconfirm,
  Segmented,
  Tooltip,
} from 'antd';
import React, { useState } from 'react';
import Panel from '@/components/Panel';
import { formatCron } from '../cron';
import type { ScheduleJob, ScheduleJobSubmit } from '../types';
import { parseForms } from '../types';
import JobEditDrawer from './JobEditDrawer';

interface JobTableProps {
  jobs: ScheduleJob[];
  loading: boolean;
  onCreate: (job: ScheduleJobSubmit) => Promise<unknown>;
  onUpdate: (id: number, job: ScheduleJobSubmit) => Promise<unknown>;
  onDelete: (id: number) => Promise<unknown>;
  creating: boolean;
  updating: boolean;
  deleting: boolean;
  onBatchAction: (action: string, ids: number[]) => Promise<void>;
  batchActioning: boolean;
}

type StatusFilter = 'all' | 'enabled' | 'disabled';

const isDefaultJob = (name: string) => name === 'default_incremental';

const JobTable: React.FC<JobTableProps> = ({
  jobs,
  loading,
  onCreate,
  onUpdate,
  onDelete,
  creating,
  updating,
  deleting,
  onBatchAction,
  batchActioning,
}) => {
  const { message } = App.useApp();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [editingJob, setEditingJob] = useState<ScheduleJob | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const filteredJobs = jobs.filter((job) => {
    if (statusFilter === 'enabled' && !job.enabled) return false;
    if (statusFilter === 'disabled' && job.enabled) return false;
    if (!search) return true;
    const keyword = search.toLowerCase();
    const forms = parseForms(job.forms).join(' ');
    return (
      job.name.toLowerCase().includes(keyword) ||
      forms.toLowerCase().includes(keyword) ||
      formatCron(job.cron_expr).toLowerCase().includes(keyword)
    );
  });

  const visibleSelectedCount = filteredJobs.filter((job) =>
    selectedIds.has(job.id),
  ).length;
  const allVisibleSelected =
    filteredJobs.length > 0 && visibleSelectedCount === filteredJobs.length;

  const openEditor = (job: ScheduleJob | null) => {
    setEditingJob(job);
    setDrawerVisible(true);
  };

  const toggleSelected = (id: number) => {
    setSelectedIds((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSubmit = async (data: ScheduleJobSubmit) => {
    try {
      if (editingJob) {
        await onUpdate(editingJob.id, data);
        message.success('任务已更新');
      } else {
        await onCreate(data);
        message.success('任务已创建');
      }
      setDrawerVisible(false);
      setEditingJob(null);
    } catch {}
  };

  const runBatch = async (
    action: 'enable' | 'disable' | 'delete',
    successText: string,
  ) => {
    if (selectedIds.size === 0) return;
    try {
      await onBatchAction(action, Array.from(selectedIds));
      message.success(successText);
      setSelectedIds(new Set());
    } catch {}
  };

  return (
    <>
      <Panel
        title={
          <span className="schedule-list-title">
            定时任务
            <span>
              {filteredJobs.length} / {jobs.length}
            </span>
          </span>
        }
        loading={loading}
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => openEditor(null)}
            loading={creating && !drawerVisible}
          >
            新建任务
          </Button>
        }
      >
        <div className="schedule-jobs-content">
          <div className="filter-toolbar schedule-filter-toolbar">
            <Input
              placeholder="搜索任务、表单或执行频率"
              prefix={<SearchOutlined />}
              allowClear
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="schedule-search"
              aria-label="搜索定时任务"
            />
            <Segmented
              value={statusFilter}
              onChange={(value) => setStatusFilter(value as StatusFilter)}
              options={[
                { label: `全部 ${jobs.length}`, value: 'all' },
                {
                  label: `已启用 ${jobs.filter((job) => job.enabled).length}`,
                  value: 'enabled',
                },
                {
                  label: `已停用 ${jobs.filter((job) => !job.enabled).length}`,
                  value: 'disabled',
                },
              ]}
            />
            <Checkbox
              checked={allVisibleSelected}
              indeterminate={visibleSelectedCount > 0 && !allVisibleSelected}
              disabled={filteredJobs.length === 0}
              onChange={(event) => {
                setSelectedIds((previous) => {
                  const next = new Set(previous);
                  for (const job of filteredJobs) {
                    if (event.target.checked) next.add(job.id);
                    else next.delete(job.id);
                  }
                  return next;
                });
              }}
              className="schedule-select-all"
            >
              选择当前结果
            </Checkbox>
          </div>

          <div
            className={`schedule-batch-bar${selectedIds.size > 0 ? ' has-selection' : ''}`}
            aria-live="polite"
          >
            {selectedIds.size > 0 ? (
              <>
                <span>
                  已选择 <strong>{selectedIds.size}</strong> 个任务
                </span>
                <div>
                  <Button
                    size="small"
                    icon={<PlayCircleOutlined />}
                    onClick={() => runBatch('enable', '已批量启用')}
                    loading={batchActioning}
                  >
                    启用
                  </Button>
                  <Button
                    size="small"
                    icon={<PauseCircleOutlined />}
                    onClick={() => runBatch('disable', '已批量禁用')}
                    loading={batchActioning}
                  >
                    停用
                  </Button>
                  <Popconfirm
                    title={`确定删除选中的 ${selectedIds.size} 个任务？`}
                    description="删除后不可恢复，请确认这些任务不再需要。"
                    onConfirm={() => runBatch('delete', '已批量删除')}
                    okText="删除"
                    cancelText="取消"
                  >
                    <Button
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      loading={batchActioning}
                    >
                      删除
                    </Button>
                  </Popconfirm>
                  <Tooltip title="清除选择">
                    <Button
                      size="small"
                      type="text"
                      aria-label="清除选择"
                      icon={<CloseOutlined />}
                      onClick={() => setSelectedIds(new Set())}
                    />
                  </Tooltip>
                </div>
              </>
            ) : (
              <span className="schedule-batch-hint">
                勾选任务后可批量启用、停用或删除
              </span>
            )}
          </div>

          {filteredJobs.length === 0 ? (
            <div className="schedule-empty">
              <CalendarOutlined />
              <strong>
                {search || statusFilter !== 'all'
                  ? '没有匹配的任务'
                  : '暂无定时任务'}
              </strong>
              <span>
                {search || statusFilter !== 'all'
                  ? '尝试调整搜索关键词或状态筛选'
                  : '新建任务后，即可按计划自动执行数据同步'}
              </span>
              {!search && statusFilter === 'all' && (
                <Button
                  type="primary"
                  ghost
                  icon={<PlusOutlined />}
                  onClick={() => openEditor(null)}
                >
                  新建第一个任务
                </Button>
              )}
            </div>
          ) : (
            <div className="schedule-job-list">
              {filteredJobs.map((job) => {
                const jobForms = parseForms(job.forms);
                const selected = selectedIds.has(job.id);
                return (
                  <div
                    key={job.id}
                    className={`schedule-job-card interactive-list${selected ? ' is-selected' : ''}${!job.enabled ? ' is-disabled' : ''}`}
                  >
                    <div className="schedule-job-select">
                      <Checkbox
                        checked={selected}
                        onChange={() => toggleSelected(job.id)}
                        aria-label={`选择任务 ${job.name}`}
                      />
                    </div>
                    <button
                      type="button"
                      className="schedule-job-main"
                      aria-label={`编辑任务 ${job.name}`}
                      onClick={() => openEditor(job)}
                    >
                      <div className="schedule-job-heading">
                        <div className="schedule-job-name">
                          <span
                            className={`schedule-job-state${job.enabled ? ' is-enabled' : ''}`}
                          />
                          <strong>{job.name}</strong>
                          {isDefaultJob(job.name) && (
                            <span className="schedule-job-badge is-default">
                              默认
                            </span>
                          )}
                        </div>
                        <div className="schedule-job-tags">
                          <span
                            className={`schedule-job-badge is-${job.sync_type}`}
                          >
                            {job.sync_type === 'incremental'
                              ? '增量同步'
                              : '全量同步'}
                          </span>
                          <span
                            className={`schedule-job-badge${job.enabled ? ' is-enabled' : ' is-disabled'}`}
                          >
                            {job.enabled ? '已启用' : '已停用'}
                          </span>
                        </div>
                      </div>
                      <div className="schedule-job-details">
                        <div className="schedule-job-frequency">
                          <ClockCircleOutlined />
                          <div>
                            <span>执行频率</span>
                            <strong title={job.cron_expr}>
                              {formatCron(job.cron_expr)}
                            </strong>
                          </div>
                        </div>
                        <div className="schedule-job-next">
                          <CalendarOutlined />
                          <div>
                            <span>下一次执行</span>
                            <strong>{job.next_run_at || '暂未安排'}</strong>
                          </div>
                        </div>
                        <div className="schedule-job-forms">
                          <span>同步范围</span>
                          <div>
                            {jobForms.length === 0 ? (
                              <span className="schedule-form-chip">
                                全部已启用表单
                              </span>
                            ) : (
                              <>
                                {jobForms.slice(0, 2).map((form) => (
                                  <span
                                    key={form}
                                    className="schedule-form-chip"
                                  >
                                    {form}
                                  </span>
                                ))}
                                {jobForms.length > 2 && (
                                  <span
                                    className="schedule-form-more"
                                    title={jobForms.join('、')}
                                  >
                                    +{jobForms.length - 2}
                                  </span>
                                )}
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                      {(job.last_run_at || job.last_status) && (
                        <div className="schedule-job-last-run">
                          <span>上次执行 {job.last_run_at || '-'}</span>
                          {job.last_status && (
                            <span className={`is-${job.last_status}`}>
                              {job.last_status === 'success' ? (
                                <CheckCircleOutlined />
                              ) : null}
                              {job.last_status}
                            </span>
                          )}
                        </div>
                      )}
                    </button>
                    <div className="schedule-job-actions">
                      <Tooltip title="编辑任务">
                        <Button
                          type="text"
                          aria-label={`编辑 ${job.name}`}
                          icon={<EditOutlined />}
                          onClick={() => openEditor(job)}
                        />
                      </Tooltip>
                      {!isDefaultJob(job.name) && (
                        <Popconfirm
                          title="确定删除该定时任务？"
                          description="删除后不可恢复。"
                          onConfirm={async () => {
                            try {
                              await onDelete(job.id);
                              message.success('任务已删除');
                            } catch {}
                          }}
                          okText="删除"
                          cancelText="取消"
                        >
                          <Tooltip title="删除任务">
                            <Button
                              type="text"
                              danger
                              aria-label={`删除 ${job.name}`}
                              icon={<DeleteOutlined />}
                              loading={deleting}
                            />
                          </Tooltip>
                        </Popconfirm>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Panel>

      <JobEditDrawer
        visible={drawerVisible}
        job={editingJob}
        allJobs={jobs}
        onSubmit={handleSubmit}
        onCancel={() => {
          setDrawerVisible(false);
          setEditingJob(null);
        }}
        submitting={editingJob ? updating : creating}
      />
    </>
  );
};

export default JobTable;
