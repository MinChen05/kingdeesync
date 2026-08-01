import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import SyncTypeTag from './SyncTypeTag';

describe('SyncTypeTag', () => {
  it('类型 "incremental" 显示 "增量"', () => {
    render(<SyncTypeTag type="incremental" />);
    expect(screen.getByText('增量')).toBeInTheDocument();
  });

  it('类型 "full" 显示 "全量"', () => {
    render(<SyncTypeTag type="full" />);
    expect(screen.getByText('全量')).toBeInTheDocument();
  });

  it('类型 "reset" 显示 "重置"', () => {
    render(<SyncTypeTag type="reset" />);
    expect(screen.getByText('重置')).toBeInTheDocument();
  });

  it('对未知类型显示该类型名', () => {
    render(<SyncTypeTag type="custom_type" />);
    expect(screen.getByText('custom_type')).toBeInTheDocument();
  });

  it('对 undefined 显示 "-"', () => {
    render(<SyncTypeTag />);
    expect(screen.getByText('-')).toBeInTheDocument();
  });

  it('对空字符串显示 "-"', () => {
    render(<SyncTypeTag type="" />);
    expect(screen.getByText('-')).toBeInTheDocument();
  });
});
