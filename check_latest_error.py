import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

log_path = r"D:\金蝶数据同步工具\logs\app.log"
with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Find the latest sync run (after 16:47)
print("=== 最近一次同步中生产订单主表的错误详情 ===")
for i in range(len(lines)-1, max(0, len(lines)-200), -1):
    line = lines[i]
    if '生产订单主表' in line or 'prd_mo' in line:
        if any(kw in line for kw in ['ERROR', 'WARNING', '截断', '失败', 'failed', 'write_failure']):
            print(line.rstrip()[:400])
