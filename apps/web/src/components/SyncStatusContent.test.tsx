import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  SyncStatusContent,
  syncIconForStatus,
  syncButtonBg,
  syncButtonBorder,
} from './SyncStatusContent';

const baseInfo = {
  progress: 50,
  current_form: 't_BD_Material',
  message: '',
  elapsed_seconds: 30,
};

describe('SyncStatusContent', () => {
  it('shows "同步进行中" for running status', () => {
    render(<SyncStatusContent status="running" {...baseInfo} />);
    expect(screen.getByText('同步进行中')).toBeInTheDocument();
  });

  it('shows current form for running status', () => {
    render(<SyncStatusContent status="running" {...baseInfo} />);
    expect(screen.getByText('当前：t_BD_Material')).toBeInTheDocument();
  });

  it('shows elapsed time for running status', () => {
    render(<SyncStatusContent status="running" {...baseInfo} />);
    expect(screen.getByText('已运行：30秒')).toBeInTheDocument();
  });

  it('shows "同步完成" for success status', () => {
    render(<SyncStatusContent status="success" {...baseInfo} />);
    expect(screen.getByText('同步完成')).toBeInTheDocument();
  });

  it('shows "同步失败" for failed status', () => {
    render(
      <SyncStatusContent
        status="failed"
        message="connection timeout"
        progress={baseInfo.progress}
        current_form={baseInfo.current_form}
        elapsed_seconds={baseInfo.elapsed_seconds}
      />,
    );
    expect(screen.getByText('同步失败')).toBeInTheDocument();
  });

  it('shows "同步失败" for failed_abnormal_exit status', () => {
    render(<SyncStatusContent status="failed_abnormal_exit" {...baseInfo} />);
    expect(screen.getByText('同步失败')).toBeInTheDocument();
  });
});

describe('syncIconForStatus', () => {
  it('returns non-null for running', () => {
    expect(syncIconForStatus('running')).not.toBeNull();
  });

  it('returns non-null for success', () => {
    expect(syncIconForStatus('success')).not.toBeNull();
  });

  it('returns non-null for failed', () => {
    expect(syncIconForStatus('failed')).not.toBeNull();
  });

  it('returns null for idle', () => {
    expect(syncIconForStatus('idle')).toBeNull();
  });
});

describe('syncButtonBg', () => {
  it('returns surface color for running', () => {
    expect(syncButtonBg('running')).toBe('var(--tk-surface)');
  });

  it('returns success color for success', () => {
    expect(syncButtonBg('success')).toBe('#064e3b');
  });

  it('returns error color for failed', () => {
    expect(syncButtonBg('failed')).toBe('#7f1d1d');
  });
});

describe('syncButtonBorder', () => {
  it('returns primary color for running', () => {
    expect(syncButtonBorder('running')).toBe('var(--tk-primary)');
  });

  it('returns success color for success', () => {
    expect(syncButtonBorder('success')).toBe('var(--tk-success)');
  });

  it('returns error color for failed', () => {
    expect(syncButtonBorder('failed')).toBe('var(--tk-error)');
  });
});
