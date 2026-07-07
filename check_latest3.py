import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

log_path = r"D:\金蝶数据同步工具\logs\app.log"
with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Find errors and warnings around 16:46~16:48
print("=== 16:46~16:48 ERROR/WARNING 日志 ===")
for i in range(len(lines)-1, -1, -1):
    if any(t in lines[i] for t in ['16:46:', '16:47:', '16:48:']):
        if any(kw in lines[i] for kw in ['ERROR', 'WARNING', 'failed', '失败', '截断', '异常', 'traceback']):
            print(lines[i].rstrip()[:500])
