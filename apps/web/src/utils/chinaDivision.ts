// Stub file for cloudflare-worker geographic route
// Not used by main application (原因：geographic 功能未实现，仅存根以消除 TS 错误)

export const provinceOptions: { label: string; value: string }[] = [];

export function getCityOptions(_province: string): { label: string; value: string }[] {
  return [];
}
