import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

log_path = r"D:\金蝶数据同步工具\logs\app.log"
with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Find the latest production order sync (around 16:47-16:48)
print("=== 16:47~16:48 同步中 prd_mo 的完整日志 ===")
for i in range(len(lines)-1, -1, -1):
    if '16:47' in lines[i] or '16:48' in lines[i]:
        if '生产订单主表' in lines[i] or 'prd_mo' in lines[i] or '写入完成' in lines[i] or '已加载' in lines[i]:
            print(lines[i].rstrip()[:400])
