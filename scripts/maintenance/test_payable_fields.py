import sys
sys.path.insert(0, '.')

from src.core.kingdee_api import kingdee_client
from src.config.config_manager import config_manager

print("正在登录...")
if not kingdee_client.login():
    print("登录失败")
    sys.exit(1)

print("登录成功\n")

form_queries = config_manager.get_form_queries()
payable_config = form_queries.get("应付单", {})

print("FieldKeys配置:")
print(payable_config.get('FieldKeys'))
print()

test_config = payable_config.copy()
test_config['Limit'] = 1

print("查询应付单数据...")
data = kingdee_client.query_data("应付单", test_config)

if data and len(data) > 0:
    print(f"获取到 {len(data)} 条数据\n")
    record = data[0]

    print("所有字段:")
    for key, value in record.items():
        print(f"  {key}: {value}")

    print("\n检查目标字段:")
    print(f"  FENTRYDISCOUNTRATE: {record.get('FENTRYDISCOUNTRATE', '【不存在】')}")
    print(f"  FENTRYTAXRATE: {record.get('FENTRYTAXRATE', '【不存在】')}")
else:
    print("未获取到数据")

kingdee_client.logout(force=True)
print("\n完成")
