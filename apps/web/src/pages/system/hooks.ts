import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  archiveSystem,
  getDiagnostics,
  getSystemConfig,
  getVersion,
  testConnections,
} from '@/services/v1';
import type { V1Diagnostics } from '@/services/v1';
import type { ConfigData } from './types';

/** useSystemPage 返回值类型 */
interface UseSystemPageResult {
  config: ConfigData;
  configLoading: boolean;
  version: string;
  diagnostics: V1Diagnostics;
  diagLoading: boolean;
  archiveLogs: (daysToKeep: number) => Promise<unknown>;
  archiving: boolean;
  testConnections: () => Promise<unknown>;
  testing: boolean;
}

/**
 * system 页面数据 Hook — v1 版诊断，旧版配置。
 *
 * 诊断和连接测试使用 v1 API。
 * 配置和归档仍使用旧接口（v1 尚无对应端点）。
 */
export function useSystemPage(): UseSystemPageResult {
  const queryClient = useQueryClient();
  // 配置信息（v1）
  const configReq = useQuery({
    queryKey: ['v1', 'config'],
    queryFn: getSystemConfig,
  });
  const config = (configReq.data ?? {}) as ConfigData;

  // 版本信息（v1）
  const versionReq = useQuery({
    queryKey: ['v1', 'version'],
    queryFn: getVersion,
  });
  const version = versionReq.data?.version || '';

  // 诊断信息（v1）
  const diagReq = useQuery({
    queryKey: ['v1', 'diagnostics'],
    queryFn: getDiagnostics,
  });
  const diagnostics = diagReq.data ?? { kingdee_api: { status: 'unknown' }, database: { status: 'unknown' }, scheduler: { status: 'unknown' }, log_service: { status: 'unknown' } };

  // 归档日志（v1）
  const archiveReq = useMutation({
    mutationFn: (daysToKeep: number) => archiveSystem(daysToKeep),
    onSuccess: (data) => {
      // Refresh diagnostics after archive
      queryClient?.invalidateQueries({ queryKey: ['v1', 'diagnostics'] });
    },
  });

  // 测试连接（v1）
  const testReq = useMutation({
    mutationFn: testConnections,
    onSuccess: () => {
      queryClient?.invalidateQueries({ queryKey: ['v1', 'diagnostics'] });
    },
  });

  return {
    config,
    configLoading: configReq.isPending,
    version,
    diagnostics,
    diagLoading: diagReq.isPending,
    archiveLogs: archiveReq.mutateAsync,
    archiving: archiveReq.isPending,
    testConnections: testReq.mutateAsync,
    testing: testReq.isPending,
  };
}
