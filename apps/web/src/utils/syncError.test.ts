import { describe, expect, it } from 'vitest';
import { ApiProblemError } from '@/services/v1';
import {
  grantQueueMessage,
  isGrantQueueBusyError,
  TARGET_DB_GRANT_QUEUE_BUSY,
} from './syncError';

describe('isGrantQueueBusyError', () => {
  it('409 + TARGET_DB_GRANT_QUEUE_BUSY 判定为排队守卫拦截', () => {
    const err = new ApiProblemError(
      409,
      TARGET_DB_GRANT_QUEUE_BUSY,
      '目标库内存授予排队 10m，本轮跳过',
    );
    expect(isGrantQueueBusyError(err)).toBe(true);
  });

  it('同为 409 的 ALREADY_RUNNING 不得误判（原因：两种 409 的等待方向不同）', () => {
    expect(
      isGrantQueueBusyError(
        new ApiProblemError(409, 'ALREADY_RUNNING', 'busy'),
      ),
    ).toBe(false);
  });

  it('同错误码但非 409 状态不得命中（原因：判定必须绑定守卫的 409 语义）', () => {
    expect(
      isGrantQueueBusyError(
        new ApiProblemError(500, TARGET_DB_GRANT_QUEUE_BUSY, 'boom'),
      ),
    ).toBe(false);
  });

  it('普通 Error / undefined / null 均不得命中', () => {
    expect(isGrantQueueBusyError(new Error(TARGET_DB_GRANT_QUEUE_BUSY))).toBe(
      false,
    );
    expect(isGrantQueueBusyError(undefined)).toBe(false);
    expect(isGrantQueueBusyError(null)).toBe(false);
  });
});

describe('grantQueueMessage', () => {
  it('优先透传服务端 message（含排队时长，不得被固定文案吞掉）', () => {
    const err = new ApiProblemError(
      409,
      TARGET_DB_GRANT_QUEUE_BUSY,
      '目标库内存授予排队 10m，本轮跳过',
    );
    expect(grantQueueMessage(err, '兜底文案')).toBe(
      '目标库内存授予排队 10m，本轮跳过',
    );
  });

  it('服务端 message 为空或纯空白时回退调用方兜底文案', () => {
    expect(
      grantQueueMessage(
        new ApiProblemError(409, TARGET_DB_GRANT_QUEUE_BUSY, ''),
        '兜底',
      ),
    ).toBe('兜底');
    expect(
      grantQueueMessage(
        new ApiProblemError(409, TARGET_DB_GRANT_QUEUE_BUSY, '   '),
        '兜底',
      ),
    ).toBe('兜底');
  });

  it('非 ApiProblemError 亦回退兜底（防御性：调用点类型可能退化）', () => {
    expect(grantQueueMessage(new Error('network'), '兜底')).toBe('兜底');
  });
});
