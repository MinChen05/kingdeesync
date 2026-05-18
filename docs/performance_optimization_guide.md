# 完全同步性能优化指南

## 一、当前性能瓶颈

### 1. 金蝶 API 查询速度
- **当前配置**：`rate_limit_qps = 10`（每秒10次请求）
- **瓶颈**：API 限流是最大的性能瓶颈
- **优化方向**：提高 QPS 限制（需要金蝶服务器支持）

### 2. 网络 I/O
- **瓶颈**：大量数据通过网络传输
- **优化方向**：增加分页大小，减少请求次数

### 3. 数据库写入速度
- **当前配置**：`insert_threads = 8`，`batch_size = 50000`
- **瓶颈**：SQL Server 写入速度
- **优化方向**：使用 staging 表批量写入

## 二、推荐优化配置

### 配置文件优化（config.ini）

```ini
[KINGDEE]
# 提高 API 请求速率（根据服务器承受能力调整，建议从 15 开始测试）
rate_limit_qps = 15

# 增加分页大小，减少请求次数（如果服务器支持）
page_size = 100000

# 启用分页（对大表单很重要）
pagination_enabled = true

# 增加请求超时时间以适应大分页
request_read_timeout = 180
max_request_read_timeout = 600

[SQLSERVER]
# 保持高并发写入
insert_threads = 8

# 增加批次大小（对大表单）
batch_size = 100000

# 启用 staging 表（已启用，保持）
use_staging = true

# 对所有大表强制使用 staging
force_staging_tables = saleorder,sal_outstock,sal_returnstock,sal_deliverynotice,pln_forecast,prd_instock,prd_mo,prd_moentry,prd_ppbom,prd_ppbomentry,eng_bom,eng_bomchild,stk_inventory,pur_purchaseorder,sub_subreqorder,bd_material

# 降低索引创建阈值，提升 MERGE 速度
stage_index_threshold = 20000

[SYNC]
# 保持最大表级并发
table_concurrency = 8

# 增加查询并发（用于分页查询）
fetch_concurrency = 8
```

## 三、分阶段优化策略

### 阶段 1：保守优化（风险低）
```ini
rate_limit_qps = 12
page_size = 75000
batch_size = 75000
```
**预期提升**：20-30%

### 阶段 2：激进优化（需要测试）
```ini
rate_limit_qps = 20
page_size = 100000
batch_size = 100000
stage_index_threshold = 15000
```
**预期提升**：40-60%

### 阶段 3：极限优化（需要服务器支持）
```ini
rate_limit_qps = 30
page_size = 150000
batch_size = 150000
insert_threads = 12
table_concurrency = 12
```
**预期提升**：80-100%

## 四、监控指标

优化后需要监控以下指标：

1. **API 响应时间**：确保不超时
2. **数据库 CPU/内存使用率**：确保不超过 80%
3. **网络带宽使用**：确保不饱和
4. **错误率**：确保 < 1%

## 五、特定表单优化

### 大表单（> 100万条记录）
- 即时库存（stk_inventory）
- 物料清单（bd_material）
- 销售订单（saleorder）

**优化策略**：
```ini
# 强制使用 staging + 大批次
batch_size = 150000
use_staging = true
```

### 小表单（< 10万条记录）
**优化策略**：
```ini
# 使用普通 MERGE，避免 staging 开销
batch_size = 10000
```

## 六、实施步骤

1. **备份当前配置**
2. **应用阶段 1 优化**
3. **运行完全同步测试**
4. **监控性能指标**
5. **如果稳定，继续阶段 2**
6. **重复测试和监控**

## 七、回滚方案

如果出现问题，立即恢复到以下安全配置：
```ini
rate_limit_qps = 10
page_size = 50000
batch_size = 50000
insert_threads = 8
table_concurrency = 8
```
