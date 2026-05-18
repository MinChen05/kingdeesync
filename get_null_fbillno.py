"""从金蝶API获取FBILLNO为空的生产订单数据"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config.config_manager import config_manager
from src.core.kingdee_api import kingdee_client

# 登录
if not kingdee_client.login():
    print("登录失败")
    sys.exit(1)

print("正在查询生产订单主表...")

# 获取查询参数
form_queries = config_manager.get_form_queries()
query_params = form_queries.get("生产订单主表", {}).copy()
query_params["Limit"] = 1000  # 取1000条

# 查询数据
data = kingdee_client.query_data("生产订单主表", query_params)

if not data:
    print("未查询到数据")
    sys.exit(0)

print(f"查询到 {len(data)} 条记录")

# 筛选FBILLNO为空的记录
null_records = []
for item in data:
    if isinstance(item, dict):
        fbillno = item.get("FBILLNO")
        if not fbillno or fbillno == "" or fbillno is None:
            null_records.append(item)
    elif isinstance(item, list):
        fbillno = item[3] if len(item) > 3 else None
        if not fbillno or fbillno == "":
            null_records.append(item)

print(f"FBILLNO为空: {len(null_records)} 条")

if null_records:
    print("\n前5条空数据:")
    for i, item in enumerate(null_records[:5]):
        if isinstance(item, dict):
            print(f"\n记录 #{i + 1}:")
            print(f"  FID: {item.get('FID')}")
            print(f"  FBILLNO: {item.get('FBILLNO')}")
            print(f"  FDATE: {item.get('FDATE')}")
            print(f"  FMATERIALID.FNUMBER: {item.get('FMATERIALID.FNUMBER')}")
        else:
            print(f"\n记录 #{i + 1}: {item[:5]}")

    # 保存到文件
    with open("null_fbillno_data.json", "w", encoding="utf-8") as f:
        json.dump(null_records, f, ensure_ascii=False, indent=2, default=str)
    print("\n完整数据已保存到: null_fbillno_data.json")
else:
    print("未发现FBILLNO为空的记录")
