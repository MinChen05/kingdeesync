import { act, fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import FormConfigDrawer from './FormConfigDrawer';

describe('FormConfigDrawer', () => {
  it('连续编辑字段映射并提交完整配置', async () => {
    const onSubmit = vi.fn();

    render(
      <FormConfigDrawer
        visible
        form={{
          form_name: '销售订单',
          enabled: true,
          form_id: 'SAL_SaleOrder',
          field_keys: 'FBillNo, FSaleOrgId',
          filter_string: 'FDocumentStatus = C',
          field_map: { FSaleOrgId: 'sale_org_id' },
        }}
        submitting={false}
        onCancel={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    const sourceInput = await screen.findByLabelText('第 1 行源字段');
    const targetInput = screen.getByLabelText('第 1 行目标列');

    act(() => {
      sourceInput.focus();
    });
    await act(async () => {
      fireEvent.change(sourceInput, { target: { value: 'FCustomerId' } });
    });
    expect(sourceInput).toHaveFocus();
    await act(async () => {
      fireEvent.change(targetInput, { target: { value: 'customer_id' } });
    });
    fireEvent.click(screen.getByRole('button', { name: '保存配置' }));

    expect(onSubmit).toHaveBeenCalledWith({
      form_id: 'SAL_SaleOrder',
      field_keys: 'FBillNo, FSaleOrgId',
      filter_string: 'FDocumentStatus = C',
      field_map: { FCustomerId: 'customer_id' },
    });
  });
});
