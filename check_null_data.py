"""检查金蝶数据中的空值"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config.config_manager import config_manager
from src.core.kingdee_api import kingdee_client


def check_null_data():
    """检查生产订单和预测订单中的空值"""

    # 登录
    if not kingdee_client.login():
        print("登录失败")
        return

    print("=" * 60)
    print("检查金蝶数据中的空值")
    print("=" * 60)

    # 检查生产订单主表
    print("\n【生产订单主表】")
    form_queries = config_manager.get_form_queries()
    query_params = form_queries.get("生产订单主表", {}).copy()
    query_params["Limit"] = 500  # 只取500条

    data = kingdee_client.query_data("生产订单主表", query_params)

    if data:
        null_fbillno = []
        for idx, item in enumerate(data):
            fbillno = item.get("FBILLNO") if isinstance(item, dict) else (item[3] if len(item) > 3 else None)
            if not fbillno:
                null_fbillno.append(
                    {
                        "index": idx,
                        "FID": item.get("FID") if isinstance(item, dict) else item[0],
                        "FBILLNO": fbillno,
                        "data": item,
                    }
                )

        print(f"总记录数: {len(data)}")
        print(f"FBILLNO 为空: {len(null_fbillno)} 条")

        if null_fbillno:
            print("\n前5条空数据:")
            for item in null_fbillno[:5]:
                print(f"  - FID: {item['FID']}, FBILLNO: {item['FBILLNO']}")

            # 保存到文件
            with open("null_prd_mo.json", "w", encoding="utf-8") as f:
                json.dump(null_fbillno, f, ensure_ascii=False, indent=2, default=str)
            print("\n完整数据已保存到: null_prd_mo.json")

    # 检查预测订单
    print("\n【预测订单】")
    query_params = form_queries.get("预测订单", {}).copy()
    query_params["Limit"] = 500

    data = kingdee_client.query_data("预测订单", query_params)

    if data:
        long_fields = []
        for idx, item in enumerate(data):
            if isinstance(item, dict):
                for key, value in item.items():
                    if isinstance(value, str) and len(value) > 256:
                        long_fields.append(
                            {"index": idx, "field": key, "length": len(value), "value": value[:100] + "..."}
                        )
            elif isinstance(item, list):
                for i, value in enumerate(item):
                    if isinstance(value, str) and len(value) > 256:
                        long_fields.append(
                            {"index": idx, "field_index": i, "length": len(value), "value": value[:100] + "..."}
                        )

        print(f"总记录数: {len(data)}")
        print(f"超长字段 (>256): {len(long_fields)} 个")

        if long_fields:
            print("\n前5个超长字段:")
            for item in long_fields[:5]:
                print(
                    f"  - 记录#{item['index']}, 字段: {item.get('field', item.get('field_index'))}, 长度: {item['length']}"
                )
                print(f"    内容: {item['value']}")

            # 保存到文件
            with open("long_pln_forecast.json", "w", encoding="utf-8") as f:
                json.dump(long_fields, f, ensure_ascii=False, indent=2, default=str)
            print("\n完整数据已保存到: long_pln_forecast.json")

    print("\n" + "=" * 60)
    print("检查完成")


if __name__ == "__main__":
    try:
        check_null_data()
    except Exception as e:
        print(f"错误: {e}")
        import traceback

        traceback.print_exc()
