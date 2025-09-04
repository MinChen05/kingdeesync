#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产订单表字段更新脚本
根据金蝶API字段映射更新生产订单表结构
"""

import os
import sys
import pymysql
import argparse
from typing import List, Dict, Any, Tuple

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入配置管理器
from src.config.config_manager import config_manager

# 数据库字段与金蝶API字段映射关系
FIELD_MAPPING = {
    # 数据库字段名: (金蝶API字段名, 数据类型, 是否允许为空, 默认值)
    "fid": ("FID", "int(11)", "NO", None),
    "fentryid": ("FTreeEntity_FENTRYID", "int(11)", "YES", None),
    "fseq": ("FTreeEntity_FSEQ", "int(11)", "YES", None),
    "fbillno": ("FBILLNO", "varchar(80)", "YES", None),
    "fbilltype": ("FBILLTYPE.FNAME", "varchar(36)", "YES", None),
    "fmaterialnumber": ("FMATERIALID.FNUMBER", "varchar(80)", "YES", None),
    "fworkshopname": ("FWorkShopID.FNAME", "varchar(100)", "YES", None),
    "fdate": ("FDATE", "datetime", "YES", None),
    "fqty": ("FQTY", "decimal(18,6)", "YES", None),
    "fsaleorderid": ("FSALEORDERID", "varchar(36)", "YES", None),
    "fsrcbillno": ("FSRCBILLNO", "varchar(80)", "YES", None),
    "fplanstartdate": ("FPLANSTARTDATE", "datetime", "YES", None),
    "fplanfinishdate": ("FPLANFINISHDATE", "datetime", "YES", None),
    "fmodifydate": ("FMODIFYDATE", "datetime", "YES", None),
    "fcancelstatus": ("FCANCELSTATUS", "char(1)", "YES", None),
    "sync_time": (None, "datetime", "YES", "CURRENT_TIMESTAMP"),
}

# 当前生产订单表结构
CURRENT_FIELDS = [
    "fid", "fbillno", "fbilltype", "fdate", "fmodifydate", "fcancelstatus", "sync_time"
]

class ProductionOrderTableUpdater:
    """生产订单表结构更新器"""
    
    def __init__(self):
        """初始化数据库连接"""
        self.config = config_manager.get_mysql_config()
        self.conn = None
        self.cursor = None
        self.table_name = "prd_mo"
        
    def connect(self):
        """连接数据库"""
        try:
            self.conn = pymysql.connect(
                host=self.config['host'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database'],
                port=int(self.config['port']),
                charset=self.config['charset']
            )
            self.cursor = self.conn.cursor()
            print(f"✅ 成功连接到数据库 {self.config['database']}")
            return True
        except Exception as e:
            print(f"❌ 数据库连接失败: {str(e)}")
            return False
    
    def close(self):
        """关闭数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("✅ 数据库连接已关闭")
    
    def get_current_fields(self) -> List[str]:
        """获取当前表的字段列表"""
        try:
            self.cursor.execute(f"DESCRIBE {self.table_name}")
            fields = [row[0] for row in self.cursor.fetchall()]
            return fields
        except Exception as e:
            print(f"❌ 获取表字段失败: {str(e)}")
            return []
    
    def add_field(self, field_name: str) -> bool:
        """添加字段到表"""
        field_info = FIELD_MAPPING.get(field_name)
        if not field_info:
            print(f"❌ 未找到字段 {field_name} 的映射信息")
            return False
        
        _, data_type, is_null, default = field_info
        null_str = "NULL" if is_null == "YES" else "NOT NULL"
        default_str = f"DEFAULT {default}" if default else ""
        
        sql = f"ALTER TABLE {self.table_name} ADD COLUMN {field_name} {data_type} {null_str} {default_str}"
        
        try:
            self.cursor.execute(sql)
            self.conn.commit()
            print(f"✅ 成功添加字段: {field_name} ({data_type})")
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"❌ 添加字段 {field_name} 失败: {str(e)}")
            return False
    
    def drop_field(self, field_name: str) -> bool:
        """从表中删除字段"""
        if field_name in ["fid", "sync_time"]:
            print(f"⚠️ 不能删除核心字段: {field_name}")
            return False
        
        sql = f"ALTER TABLE {self.table_name} DROP COLUMN {field_name}"
        
        try:
            self.cursor.execute(sql)
            self.conn.commit()
            print(f"✅ 成功删除字段: {field_name}")
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"❌ 删除字段 {field_name} 失败: {str(e)}")
            return False
    
    def update_table_structure(self, fields_to_keep: List[str]):
        """更新表结构"""
        if not self.connect():
            return
        
        try:
            # 获取当前表字段
            current_fields = self.get_current_fields()
            print(f"当前表 {self.table_name} 的字段: {', '.join(current_fields)}")
            
            # 添加新字段
            for field in fields_to_keep:
                if field not in current_fields and field in FIELD_MAPPING:
                    self.add_field(field)
            
            # 删除不需要的字段
            for field in current_fields:
                if field not in fields_to_keep and field != "sync_time" and field != "fid":
                    self.drop_field(field)
            
            print(f"\n✅ 表 {self.table_name} 结构更新完成")
            
            # 获取更新后的字段
            updated_fields = self.get_current_fields()
            print(f"更新后的字段: {', '.join(updated_fields)}")
            
            # 更新配置管理器中的FieldKeys
            self.update_config_field_keys(fields_to_keep)
            
        except Exception as e:
            print(f"❌ 更新表结构失败: {str(e)}")
        finally:
            self.close()
    
    def update_config_field_keys(self, fields: List[str]):
        """更新配置管理器中的FieldKeys"""
        try:
            # 构建新的FieldKeys
            field_keys = []
            for field in fields:
                if field in FIELD_MAPPING and FIELD_MAPPING[field][0]:
                    field_keys.append(FIELD_MAPPING[field][0])
            
            field_keys_str = ",".join(field_keys)
            print(f"\n新的FieldKeys: {field_keys_str}")
            print("\n请手动更新 src/config/config_manager.py 文件中的生产订单FieldKeys配置")
            print("将以下内容复制到配置文件中:")
            print(f'"FieldKeys": "{field_keys_str}",\n')
            
        except Exception as e:
            print(f"❌ 更新FieldKeys失败: {str(e)}")
    
    def update_mysql_manager(self, fields: List[str]):
        """更新MySQL管理器中的SQL语句和数据准备函数"""
        try:
            # 构建SQL字段列表
            sql_fields = ", ".join(fields)
            sql_placeholders = ", ".join([r"%s"] * len(fields))
            sql_updates = ", ".join([f"{field} = VALUES({field})" for field in fields if field != "fid"])
            
            sql_template = f"""
            INSERT INTO {self.table_name} (
                {sql_fields}
            ) VALUES (
                {sql_placeholders}
            ) ON DUPLICATE KEY UPDATE
                {sql_updates}
            """
            
            print("\n请手动更新 src/core/mysql_manager.py 文件中的insert_production_orders函数")
            print("将以下SQL语句复制到函数中:")
            print(sql_template)
            
            # 构建数据准备函数代码
            dict_format_items = []
            list_format_items = []
            
            for i, field in enumerate(fields):
                if field in FIELD_MAPPING and FIELD_MAPPING[field][0]:
                    api_field = FIELD_MAPPING[field][0]
                    if "." in api_field:
                        dict_format_items.append(f"item.get('{api_field}'),  # {field}")
                    else:
                        dict_format_items.append(f"item.get('{api_field}'),  # {field}")
                    
                    if field in ["fdate", "fplanstartdate", "fplanfinishdate", "fmodifydate"]:
                        list_format_items.append(f"self._parse_datetime(str(item[{i}]) if item[{i}] else None),  # {field}")
                    else:
                        list_format_items.append(f"item[{i}],  # {field}")
            
            dict_format = "\n                    ".join(dict_format_items)
            list_format = "\n                    ".join(list_format_items)
            
            prepare_func_template = f'''    def _prepare_production_order_data(self, item) -> Optional[Tuple]:
        """准备生产订单数据
        按照数据库字段顺序: {', '.join(fields)}
        """
        try:
            # 检查数据类型
            if isinstance(item, dict):
                # 字典格式数据
                return (
                    {dict_format}
                )
            elif isinstance(item, list) and len(item) >= {len(fields)}:
                # 列表格式数据（金蝶API直接返回的数组格式）
                # 根据 FieldKeys 的顺序映射到数据库字段
                return (
                    {list_format}
                )
            else:
                logger.error(f"不支持的数据类型，期望字典或列表，实际: {{type(item)}}, 内容: {{item}}")
                return None
        except Exception as e:
            logger.error(f"准备生产订单数据失败: {{str(e)}}, 数据: {{item}}")
            return None'''
            
            print("\n请手动更新 src/core/mysql_manager.py 文件中的_prepare_production_order_data函数")
            print("将以下代码复制到函数中:")
            print(prepare_func_template)
            
        except Exception as e:
            print(f"❌ 生成更新代码失败: {str(e)}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="生产订单表字段更新工具")
    parser.add_argument("--add", nargs="*", help="要添加的字段列表")
    parser.add_argument("--remove", nargs="*", help="要删除的字段列表")
    parser.add_argument("--list", action="store_true", help="列出所有可用字段")
    parser.add_argument("--current", action="store_true", help="显示当前表字段")
    parser.add_argument("--update-all", action="store_true", help="更新为所有可用字段")
    
    args = parser.parse_args()
    
    updater = ProductionOrderTableUpdater()
    
    if args.list:
        print("可用的生产订单字段:")
        for field, info in FIELD_MAPPING.items():
            api_field, data_type, is_null, default = info
            print(f"- {field}: {data_type} ({api_field})")
        return
    
    if args.current:
        if not updater.connect():
            return
        current_fields = updater.get_current_fields()
        print(f"当前表 {updater.table_name} 的字段: {', '.join(current_fields)}")
        updater.close()
        return
    
    # 确定要保留的字段
    fields_to_keep = CURRENT_FIELDS.copy()
    
    if args.add:
        for field in args.add:
            if field in FIELD_MAPPING and field not in fields_to_keep:
                fields_to_keep.append(field)
    
    if args.remove:
        fields_to_keep = [f for f in fields_to_keep if f not in args.remove and f != "fid" and f != "sync_time"]
        # 确保必要字段不被删除
        for field in ["fid", "sync_time"]:
            if field not in fields_to_keep:
                fields_to_keep.append(field)
    
    if args.update_all:
        fields_to_keep = list(FIELD_MAPPING.keys())
    
    # 如果没有指定任何操作，显示帮助信息
    if not any([args.add, args.remove, args.list, args.current, args.update_all]):
        parser.print_help()
        return
    
    # 更新表结构
    updater.update_table_structure(fields_to_keep)
    
    # 生成更新MySQL管理器的代码
    updater.update_mysql_manager(fields_to_keep)

if __name__ == "__main__":
    main()