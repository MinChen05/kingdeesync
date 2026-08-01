# 金蝶数据同步工具 - FastAPI 接口定义草案

> 基于 DESIGN.md 设计，面向 Web/Tauri 前端，与现有 Python 后端模块对齐。

## 一、通用约定

- Base Path：`/api`
- 数据格式：JSON
- 错误响应格式：
  ```json
  {
    "ok": false,
    "error": "错误描述",
    "code": "ERROR_CODE"
  }
  ```
- 成功响应（通用）：
  ```json
  {
    "ok": true,
    "data": { ... }
  }
  ```

## 二、配置相关接口

### GET /api/config

- 说明：获取全局配置（脱敏后）
- 响应：
  ```json
  {
    "ok": true,
    "data": {
      "sync": {
        "auto_sync": false,
        "sync_interval": 120,
        "sync_type": "incremental",
        "default_forms": ["仓库", "物料"],
        "table_concurrency": 8,
        "fetch_concurrency": 4,
        "time_window_days": 30
      },
      "database": {
        "type": "sqlserver"
      },
      "retention_days": 90
    }
  }
  ```

### PUT /api/config

- 说明：更新配置
- 请求体：
  ```json
  {
    "sync": {
      "auto_sync": false,
      "sync_interval": 120,
      "sync_type": "incremental",
      "table_concurrency": 8,
      "time_window_days": 30
    },
    "retention_days": 90
  }
  ```
- 响应：
  ```json
  {
    "ok": true
  }
  ```

## 三、表单管理接口

### GET /api/forms

- 说明：获取所有可同步表单列表及映射
- 响应：
  ```json
  {
    "ok": true,
    "data": [
      {
        "form_name": "仓库",
        "table_name": "bd_stock",
        "enabled": true,
        "incremental_field": "FMODIFYDATE"
      },
      {
        "form_name": "销售订单",
        "table_name": "saleorder",
        "enabled": true,
        "incremental_field": "FModifyDate"
      }
    ]
  }
  ```

### PUT /api/forms/{form_name}

- 说明：更新单个表单配置
- 路径参数：
  - `form_name`: 表单名称
- 请求体：
  ```json
  {
    "enabled": true,
    "incremental_field": "FModifyDate"
  }
  ```
- 响应：
  ```json
  {
    "ok": true
  }
  ```

## 四、同步控制接口

### POST /api/sync/start

- 说明：启动同步任务
- 请求体：
  ```json
  {
    "forms": ["仓库", "物料", "销售订单"],
    "sync_type": "incremental"
  }
  ```
- 响应：
  ```json
  {
    "ok": true,
    "data": {
      "run_id": "9b7dcb8694b04ae49adf4c5f6f81cc17"
    }
  }
  ```

### GET /api/sync/status?run_id={run_id}

- 说明：查询同步任务状态与进度
- 参数：
  - `run_id`: 同步任务 ID
- 响应：
  ```json
  {
    "ok": true,
    "data": {
      "run_id": "9b7dcb8694b04ae49adf4c5f6f81cc17",
      "status": "running",
      "current_form": "销售订单",
      "progress": 60,
      "message": "正在同步 销售订单...",
      "started_at": "2026-07-22T22:02:53",
      "elapsed_seconds": 15
    }
  }
  ```

### POST /api/sync/stop?run_id={run_id}

- 说明：请求停止同步任务（优雅停止）
- 响应：
  ```json
  {
    "ok": true
  }
  ```

## 五、仪表盘与趋势接口

### GET /api/dashboard/today

- 说明：获取今日仪表盘统计
- 响应：
  ```json
  {
    "ok": true,
    "data": {
      "sync_count": 1,
      "sync_records": 4,
      "success_rate": 100.0,
      "fail_count": 0,
      "pending_count": 0,
      "avg_duration": 1.27,
      "last_sync_time": "2026-07-22T22:02:53",
      "yday_count": 0,
      "yday_records": 0,
      "yday_rate": 0.0,
      "yday_fail_count": 0,
      "yday_pending_count": 0,
      "yday_avg_duration": null
    }
  }
  ```

### GET /api/trend/7d

- 说明：获取近 7 天同步趋势
- 响应：
  ```json
  {
    "ok": true,
    "data": [
      {
        "day": "2026-07-16",
        "count": 2,
        "volume": 120,
        "rate": 100.0
      },
      {
        "day": "2026-07-17",
        "count": 3,
        "volume": 200,
        "rate": 66.7
      }
    ]
  }
  ```

### GET /api/top-forms/7d?limit=5

- 说明：获取近 7 天同步最多的表单
- 参数：
  - `limit`: 返回数量（默认 5）
- 响应：
  ```json
  {
    "ok": true,
    "data": [
      {
        "name": "销售订单",
        "count": 10,
        "rate": 90.0
      }
    ]
  }
  ```

## 六、历史查询接口

### GET /api/history

- 说明：分页查询同步历史
- 参数：
  - `page`: 页码（默认 1）
  - `page_size`: 每页条数（默认 20）
  - `start_date`: 起始日期（YYYY-MM-DD）
  - `end_date`: 结束日期（YYYY-MM-DD）
  - `status`: 状态过滤（success / partial / failed / failed_abnormal_exit）
  - `sync_type`: 类型过滤（incremental / complete）
  - `form_name`: 按表单名称模糊搜索
- 响应：
  ```json
  {
    "ok": true,
    "data": {
      "total": 10,
      "page": 1,
      "page_size": 20,
      "items": [
        {
          "run_id": "9b7dcb8694b04ae49adf4c5f6f81cc17",
          "sync_type": "incremental",
          "status": "success",
          "forms_synced": "仓库, 物料, 销售订单",
          "total_records": 4,
          "start_time": "2026-07-22T22:02:53",
          "end_time": "2026-07-22T22:02:55",
          "duration_seconds": 1.27,
          "message": "所有表同步成功，共同步 4 条记录"
        }
      ]
    }
  }
  ```

### GET /api/history/runs/{run_id}/details

- 说明：获取某次同步任务的详细信息
- 路径参数：
  - `run_id`: 同步任务 ID
- 响应：
  ```json
  {
    "ok": true,
    "data": {
      "run_id": "9b7dcb8694b04ae49adf4c5f6f81cc17",
      "sync_type": "incremental",
      "status": "success",
      "forms_synced": "仓库, 物料, 销售订单",
      "total_records": 4,
      "start_time": "2026-07-22T22:02:53",
      "end_time": "2026-07-22T22:02:55",
      "duration_seconds": 1.27,
      "message": "所有表同步成功，共同步 4 条记录",
      "form_stats": [
        {
          "form_name": "仓库",
          "table_name": "bd_stock",
          "fetched_count": 0,
          "inserted_count": 0,
          "error_count": 0,
          "status": "success",
          "duration_seconds": 0.12
        },
        {
          "form_name": "销售订单",
          "table_name": "saleorder",
          "fetched_count": 4,
          "inserted_count": 4,
          "error_count": 0,
          "status": "success",
          "duration_seconds": 0.44
        }
      ],
      "errors": [
        {
          "form_name": "销售订单",
          "error_type": "api_warning",
          "error_message": "第3页查询较慢，耗时超过阈值"
        }
      ]
    }
  }
  ```

## 七、统计查询接口

### GET /api/stats/summary?from={from}&to={to}

- 说明：获取指定时间范围内的任务统计汇总
- 参数：
  - `from`: 起始日期（YYYY-MM-DD）
  - `to`: 结束日期（YYYY-MM-DD）
- 响应：
  ```json
  {
    "ok": true,
    "data": {
      "total_runs": 10,
      "success_runs": 9,
      "failed_runs": 1,
      "avg_success_rate": 90.0,
      "avg_duration_seconds": 5.3
    }
  }
  ```

### GET /api/stats/forms?from={from}&to={to}&limit=20

- 说明：获取指定时间范围内的表级统计
- 参数：
  - `from`: 起始日期
  - `to`: 结束日期
  - `limit`: 返回数量（默认 20）
- 响应：
  ```json
  {
    "ok": true,
    "data": [
      {
        "form_name": "销售订单",
        "sync_count": 10,
        "total_fetched": 500,
        "total_inserted": 120,
        "total_errors": 2,
        "success_rate": 90.0
      }
    ]
  }
  ```

## 八、诊断接口

### GET /api/diagnostics

- 说明：获取系统诊断信息
- 响应：
  ```json
  {
    "ok": true,
    "data": {
      "kingdee_api": {
        "status": "ok",
        "last_test_time": "2026-07-22T22:10:00"
      },
      "database": {
        "status": "ok",
        "type": "sqlserver",
        "version": "Microsoft SQL Server ..."
      },
      "environment": {
        "python_version": "3.11.9",
        "mode": "development"
      },
      "recent_errors": [
        {
          "form_name": "销售订单",
          "error_type": "timeout",
          "error_message": "查询超时",
          "created_at": "2026-07-22T21:50:00"
        }
      ]
    }
  }
  ```

### POST /api/diagnostics/test-connections

- 说明：手动测试连接
- 响应：
  ```json
  {
    "ok": true,
    "data": {
      "kingdee_api": true,
      "database": true,
      "messages": []
    }
  }
  ```

## 九、维护接口

### POST /api/maintenance/archive

- 说明：执行运维记录归档/清理
- 请求体：
  ```json
  {
    "days_to_keep": 90
  }
  ```
- 响应：
  ```json
  {
    "ok": true
  }
  ```
