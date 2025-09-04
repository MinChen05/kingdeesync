#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产订单表重建脚本
删除并重新创建生产订单表
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
    # 数据库字段名: (金蝶API字段名, 数据类型, 是否允许为空, 默认值, 是否为主键)
    "fid": ("FID", "int(11)", "NO", None, True),
    "fentryid": ("FTreeEntity_FENTRYID", "int(11)", "YES", None, False),
    "fseq": ("FTreeEntity_FSEQ", "int(11)", "YES", None, False),
    "fbillno": ("FBILLNO", "varchar(80)", "YES", None, False),
    "fbilltype": ("FBILLTYPE.FNAME", "varchar(36)", "YES", None, False),
    "fmaterialnumber": ("FMATERIALID.FNUMBER", "varchar(80)", "YES", None, False),
    "fworkshopname": ("FWorkShopID.FNAME", "varchar(100)", "YES", None, False),
    "fdate": ("FDATE", "datetime", "YES", None, False),
    "fqty": ("FQTY", "decimal(18,6)", "YES", None, False),
    "fsaleorderid": ("FSALEORDERID", "varchar(36)", "YES", None, False),
    "fsrcbillno": ("FSRCBILLNO", "varchar(80)", "YES", None, False),
    "fplanstartdate": ("FPLANSTARTDATE", "datetime", "YES", None, False),
    "fplanfinishdate": ("FPLANFINISHDATE", "datetime", "YES", None, False),
    "fmodifydate": ("FMODIFYDATE", "datetime", "YES", None, False),
    "fcancelstatus": ("FCANCELSTATUS", "char(1)", "YES", None, False),
    "sync_time": (None, "datetime", "YES", "CURRENT_TIMESTAMP", False),
}

class ProductionOrderTableRebuild:
    """生产订单表重建器"""
    
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
    
    def table_exists(self) -> bool:
        """检查表是否存在"""
        try:
            self.cursor.execute(f"SHOW TABLES LIKE '{self.table_name}'")
            return self.cursor.fetchone() is not None
        except Exception as e:
            print(f"❌ 检查表是否存在时发生错误: {str(e)}")
            return False
    
    def drop_table(self) -> bool:
        """删除表"""
        try:
            if self.table_exists():
                self.cursor.execute(f"DROP TABLE {self.table_name}")
                self.conn.commit()
                print(f"✅ 成功删除表 {self.table_name}")
                return True
            else:
                print(f"⚠️ 表 {self.table_name} 不存在，无需删除")
                return True
        except Exception as e:
            self.conn.rollback()
            print(f"❌ 删除表 {self.table_name} 失败: {str(e)}")
            return False
    
    def create_table(self) -> bool:
        """创建表"""
        try:
            # 构建字段定义
            field_definitions = []
            primary_key = None
            
            for field_name, field_info in FIELD_MAPPING.items():
                _, data_type, is_null, default, is_primary = field_info
                null_str = "NULL" if is_null == "YES" else "NOT NULL"
                default_str = f"DEFAULT {default}" if default else ""
                
                field_def = f"{field_name} {data_type} {null_str} {default_str}"
                field_definitions.append(field_def)
                
                if is_primary:
                    primary_key = field_name
            
            # 添加主键定义
            if primary_key:
                field_definitions.append(f"PRIMARY KEY ({primary_key})")
            
            # 构建创建表SQL
            field_defs_str = ',\n                '.join(field_definitions)
            create_sql = f"""CREATE TABLE {self.table_name} (
                {field_defs_str}
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;"""
            
            self.cursor.execute(create_sql)
            self.conn.commit()
            print(f"✅ 成功创建表 {self.table_name}")
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"❌ 创建表 {self.table_name} 失败: {str(e)}")
            return False
    
    def rebuild_table(self):
        """重建表"""
        if not self.connect():
            return
        
        try:
            # 删除表
            if not self.drop_table():
                return
            
            # 创建表
            if not self.create_table():
                return
            
            print(f"\n✅ 表 {self.table_name} 重建完成")
            
            # 显示表结构
            self.cursor.execute(f"DESCRIBE {self.table_name}")
            fields = self.cursor.fetchall()
            print(f"\n表 {self.table_name} 的结构:")
            for field in fields:
                print(f"- {field[0]}: {field[1]} {field[2]} {field[3]} {field[4]} {field[5]}")
            
        except Exception as e:
            print(f"❌ 重建表结构失败: {str(e)}")
        finally:
            self.close()

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="生产订单表重建工具")
    parser.add_argument("--confirm", action="store_true", help="确认重建表（必须指定此参数才会执行重建操作）")
    
    args = parser.parse_args()
    
    if not args.confirm:
        print("⚠️ 警告: 重建表将删除所有现有数据！请使用 --confirm 参数确认操作。")
        return
    
    rebuilder = ProductionOrderTableRebuild()
    rebuilder.rebuild_table()

if __name__ == "__main__":
    main()