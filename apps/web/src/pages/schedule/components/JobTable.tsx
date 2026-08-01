import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { App, Button, Input, Popconfirm } from 'antd';
import React, { useState } from 'react';
import type { ScheduleJob, ScheduleJobSubmit } from '../types';
import { parseForms } from '../types';
import { formatCron } from '../cron';
import JobEditDrawer from './JobEditDrawer';

interface JobTableProps {
  jobs: ScheduleJob[];
  loading: boolean;
  onCreate: (job: ScheduleJobSubmit) => void;
  onUpdate: (id: number, job: ScheduleJobSubmit) => void;
  onDelete: (id: number) => void;
  creating: boolean;
  updating: boolean;
  deleting: boolean;
}

const isDefaultJob = (name: string) => name === 'default_incremental';

/** 小标签 */
const SmallTag: React.FC<{ color: string; children: React.ReactNode }> = ({ color, children }) => (
  <span
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: 44,
      height: 22,
      borderRadius: 6,
      fontSize: 11,
      fontWeight: 500,
      color,
      background: `${color}18`,
      flexShrink: 0,
    }}
  >
    {children}
  </span>
);

/**
 * 任务列表：卡片列表 + 搜索 + 编辑/删除
 */
const JobTable: React.FC<JobTableProps> = ({
  jobs,
  loading,
  onCreate,
  onUpdate,
  onDelete,
  creating,
  updating,
  deleting,
}) => {
  const { message } = App.useApp();
  const [search, setSearch] = useState('');
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [editingJob, setEditingJob] = useState<ScheduleJob | null>(null);

  const filteredJobs = jobs.filter((job) => {
    if (!search) return true;
    const s = search.toLowerCase();
    const forms = parseForms(job.forms).join(' ');
    return job.name.toLowerCase().includes(s) || forms.toLowerCase().includes(s);
  });

  const handleSubmit = (data: ScheduleJobSubmit) => {
    if (editingJob) {
      onUpdate(editingJob.id, data);
      message.success('任务已更新');
    } else {
      onCreate(data);
      message.success('任务已创建');
    }
    setDrawerVisible(false);
  };

  return (
    <>
      <div className="glass-card" style={{ padding: '20px 24px' }}>
        {/* 标题栏 */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: '#e2e8f0' }}>
            定时任务
            <span style={{ fontSize: 13, fontWeight: 400, color: 'var(--tk-dim)', marginLeft: 8 }}>
              ({jobs.length}个)
            </span>
          </span>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Input
              placeholder="搜索名称或表单"
              prefix={<SearchOutlined style={{ color: 'var(--tk-dim)' }} />}
              allowClear
              size="small"
              style={{ width: 200 }}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <Button
              type="primary"
              size="small"
              icon={<PlusOutlined />}
              onClick={() => {
                setEditingJob(null);
                setDrawerVisible(true);
              }}
              loading={creating}
            >
              新建
            </Button>
          </div>
        </div>

        {/* 任务列表 */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--tk-dim)', fontSize: 13 }}>
            加载中...
          </div>
        ) : filteredJobs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--tk-dim)', fontSize: 13 }}>
            {search ? '未找到匹配的任务' : '暂无定时任务'}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {filteredJobs.map((job) => {
              const jobForms = parseForms(job.forms);
              return (
                <div
                  key={job.id}
                  className="list-row"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 16px',
                  }}
                >
                  {/* 左侧：指示灯 + 信息 */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0, flex: 1 }}>
                    {/* 状态灯 */}
                    <div
                      className="shrink-0 rounded-full"
                      style={{
                        width: 7,
                        height: 7,
                        backgroundColor: job.enabled ? '#22c55e' : '#475569',
                        boxShadow: job.enabled ? '0 0 6px rgba(34,197,94,0.5)' : 'none',
                      }}
                    />
                    {/* 名称 + 详情 */}
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontWeight: 500, color: '#e2e8f0', fontSize: 14 }}>
                          {job.name}
                        </span>
                        {isDefaultJob(job.name) && (
                          <SmallTag color="#f59e0b">默认</SmallTag>
                        )}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 3, fontSize: 12, color: 'var(--tk-dim)' }}>
                        <span className="shrink-0">{formatCron(job.cron_expr)}</span>
                        {jobForms.length > 0 && (
                          <>
                            <span style={{ color: 'rgba(148,163,184,0.3)' }}>|</span>
                            <span className="shrink-0">{jobForms.length}</span>
                            <span>个表单</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* 右侧：标签 + 操作 */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                    <SmallTag color={job.sync_type === 'incremental' ? '#38bdf8' : '#34d399'}>
                      {job.sync_type === 'incremental' ? '增量' : '全量'}
                    </SmallTag>
                    <SmallTag color={job.enabled ? '#22c55e' : '#475569'}>
                      {job.enabled ? '启用' : '禁用'}
                    </SmallTag>
                    <Button
                      type="text"
                      size="small"
                      icon={<EditOutlined style={{ fontSize: 13 }} />}
                      style={{ color: 'var(--tk-dim)', width: 28, height: 28 }}
                      onClick={() => {
                        setEditingJob(job);
                        setDrawerVisible(true);
                      }}
                    />
                    {!isDefaultJob(job.name) && (
                      <Popconfirm
                        title="确定删除此任务？"
                        onConfirm={() => {
                          onDelete(job.id);
                          message.success('任务已删除');
                        }}
                        okText="确定"
                        cancelText="取消"
                      >
                        <Button
                          type="text"
                          size="small"
                          danger
                          icon={<DeleteOutlined style={{ fontSize: 13 }} />}
                          loading={deleting}
                          style={{ width: 28, height: 28 }}
                        />
                      </Popconfirm>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <JobEditDrawer
        visible={drawerVisible}
        job={editingJob}
        allJobs={jobs}
        onSubmit={handleSubmit}
        onCancel={() => setDrawerVisible(false)}
        submitting={editingJob ? updating : creating}
      />
    </>
  );
};

export default JobTable;
