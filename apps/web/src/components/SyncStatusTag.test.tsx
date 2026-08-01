import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import SyncStatusTag from './SyncStatusTag';

describe('SyncStatusTag', () => {
  it('状态 "success" 显示 "成功"', () => {
    render(<SyncStatusTag status="success" />);
    expect(screen.getByText('成功')).toBeInTheDocument();
  });

  it('状态 "failed" 显示 "失败"', () => {
    render(<SyncStatusTag status="failed" />);
    expect(screen.getByText('失败')).toBeInTheDocument();
  });

  it('状态 "failed_abnormal_exit" 显示 "异常退出"', () => {
    render(<SyncStatusTag status="failed_abnormal_exit" />);
    expect(screen.getByText('异常退出')).toBeInTheDocument();
  });

  it('状态 "partial" 显示 "部分完成"', () => {
    render(<SyncStatusTag status="partial" />);
    expect(screen.getByText('部分完成')).toBeInTheDocument();
  });

  it('状态 "running" 显示 "运行中"', () => {
    render(<SyncStatusTag status="running" />);
    expect(screen.getByText('运行中')).toBeInTheDocument();
  });

  it('状态 "idle" 显示 "空闲"', () => {
    render(<SyncStatusTag status="idle" />);
    expect(screen.getByText('空闲')).toBeInTheDocument();
  });

  it('对未知状态显示该状态名', () => {
    render(<SyncStatusTag status="unknown_status" />);
    expect(screen.getByText('unknown_status')).toBeInTheDocument();
  });

  it('对 undefined 显示 "未知"', () => {
    render(<SyncStatusTag />);
    expect(screen.getByText('未知')).toBeInTheDocument();
  });

  it('对空字符串显示 "未知"', () => {
    render(<SyncStatusTag status="" />);
    expect(screen.getByText('未知')).toBeInTheDocument();
  });
});
