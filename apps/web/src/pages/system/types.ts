/** 系统配置（/api/config 响应的 data 部分） */
export interface ConfigData {
  kingdee?: {
    login_url: string;
    query_url: string;
    username: string;
    acct_id: string;
    lcid: string;
    page_size: number;
    max_pages: number;
    rate_limit_qps: number;
    keep_session_alive: boolean;
    keep_alive_interval: number;
    [key: string]: unknown;
  };
  database?: {
    type: string;
    host: string;
    port: number;
    database: string;
    user: string;
    [key: string]: unknown;
  };
  sync?: {
    sync_type: string;
    sync_interval: number;
    auto_sync: boolean;
    table_concurrency: number;
    time_window_days: number;
    [key: string]: unknown;
  };
  server?: {
    host: string;
    port: number;
  };
}
