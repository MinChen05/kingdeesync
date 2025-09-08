#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产订单表字段添加脚本
为生产订单表添加FSTATUS和FSTOCKINQUAQTY字段
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

# 要添加的字段定义
NEW_FIELDS = {
    # 字段名: (数据类型, 是否允许为空, 默认值)
    "fstatus": ("CHAR(1)", "YES", None),
    "fstockinquaqty": ("DECIMAL(23,2)", "YES", None)
}

class ProductionOrderFieldAdder:
    """生产订单表字段添加器"""
    
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
    
    def check_table_exists(self) -> bool:
        """检查表是否存在"""
        try:
            self.cursor.execute(f"SHOW TABLES LIKE '{self.table_name}'")
            return self.cursor.fetchone() is not None
        except Exception as e:
            print(f"❌ 检查表是否存在失败: {str(e)}")
            return False
    
    def check_field_exists(self, field_name: str) -> bool:
        """检查字段是否存在"""
        try:
            self.cursor.execute(f"SHOW COLUMNS FROM {self.table_name} LIKE '{field_name}'")
            return self.cursor.fetchone() is not None
        except Exception as e:
            print(f"❌ 检查字段是否存在失败: {str(e)}")
            return False
    
    def add_field(self, field_name: str, data_type: str, is_null: str, default_value: Any = None) -> bool:
        """添加字段"""
        try:
            # 构建SQL语句
            sql = f"ALTER TABLE {self.table_name} ADD COLUMN {field_name} {data_type}"
            
            # 添加NULL/NOT NULL约束
            if is_null == "NO":
                sql += " NOT NULL"
            
            # 添加默认值
            if default_value is not None:
                if default_value == "CURRENT_TIMESTAMP":
                    sql += f" DEFAULT {default_value}"
                else:
                    sql += f" DEFAULT '{default_value}'"
            
            # 执行SQL
            self.cursor.execute(sql)
            self.conn.commit()
            print(f"✅ 成功添加字段 {field_name} ({data_type})")
            return True
        except Exception as e:
            print(f"❌ 添加字段失败: {str(e)}")
            self.conn.rollback()
            return False
    
    def update_mysql_manager(self):
        """更新MySQL管理器中的SQL语句和数据准备函数"""
        try:
            # 读取mysql_manager.py文件
            mysql_manager_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'core', 'mysql_manager.py')
            with open(mysql_manager_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 更新创建表SQL
            create_table_start = content.find("field_definitions = [")
            create_table_end = content.find("]\n", create_table_start)
            
            if create_table_start != -1 and create_table_end != -1:
                # 提取现有字段定义
                field_defs_str = content[create_table_start + len("field_definitions = ["):create_table_end]
                field_defs = [line.strip() for line in field_defs_str.split(",")]
                
                # 添加新字段定义
                for field_name, (data_type, is_null, default_value) in NEW_FIELDS.items():
                    field_def = f'"{field_name.upper()} {data_type} {"NULL" if is_null == "YES" else "NOT NULL"}'
                    if default_value:
                        field_def += f' DEFAULT {default_value}"'
                    else:
                        field_def += '"'
                    
                    if field_def not in field_defs:
                        field_defs.append(field_def)
                
                # 更新字段定义
                new_field_defs_str = ',\n                '.join(field_defs)
                new_content = content[:create_table_start + len("field_definitions = [")] + new_field_defs_str + content[create_table_end:]
                
                # 更新插入SQL
                insert_sql_start = content.find("INSERT INTO prd_mo (")
                insert_sql_end = content.find(") VALUES (", insert_sql_start)
                
                if insert_sql_start != -1 and insert_sql_end != -1:
                    # 提取现有字段列表
                    fields_str = content[insert_sql_start + len("INSERT INTO prd_mo ("):insert_sql_end]
                    fields = [field.strip() for field in fields_str.split(",")]
                    
                    # 添加新字段
                    for field_name in NEW_FIELDS.keys():
                        field_upper = field_name.upper()
                        if field_upper not in fields:
                            fields.append(field_upper)
                    
                    # 更新字段列表
                    new_fields_str = ", ".join(fields)
                    
                    # 更新VALUES部分
                    values_start = content.find(") VALUES (", insert_sql_start)
                    values_end = content.find(")", values_start + len(") VALUES ("))
                    
                    if values_start != -1 and values_end != -1:
                        # 提取现有值占位符
                        values_str = content[values_start + len(") VALUES ("):values_end]
                        values = [value.strip() for value in values_str.split(",")]
                        
                        # 添加新值占位符
                        for _ in range(len(fields) - len(values)):
                            values.append("%s")
                        
                        # 更新值占位符
                        new_values_str = ", ".join(values)
                        
                        # 更新ON DUPLICATE KEY UPDATE部分
                        update_start = content.find(") ON DUPLICATE KEY UPDATE", values_end)
                        update_end = content.find("\n", update_start)
                        
                        if update_start != -1 and update_end != -1:
                            # 提取现有更新语句
                            update_str = content[update_start + len(") ON DUPLICATE KEY UPDATE\n"):update_end]
                            update_lines = [line.strip() for line in update_str.split(",")]
                            
                            # 添加新字段更新
                            for field_name in NEW_FIELDS.keys():
                                field_upper = field_name.upper()
                                update_line = f"{field_upper} = VALUES({field_upper})"
                                if update_line not in update_lines:
                                    update_lines.append(update_line)
                            
                            # 更新更新语句
                            new_update_str = ",\n            ".join(update_lines)
                            
                            # 构建新的SQL语句
                            sql_part = f"INSERT INTO prd_mo (\n            {new_fields_str}\n        ) VALUES (\n            {new_values_str}\n        ) ON DUPLICATE KEY UPDATE\n            {new_update_str}"
                            
                            # 替换SQL语句
                            new_content = new_content.replace(content[insert_sql_start:update_end], sql_part)
                
                # 更新_prepare_production_order_data函数
                prepare_func_start = content.find("def _prepare_production_order_data")
                prepare_func_end = content.find("def", prepare_func_start + 1)
                
                if prepare_func_start != -1 and prepare_func_end != -1:
                    # 提取函数定义
                    func_def = content[prepare_func_start:prepare_func_end]
                    
                    # 查找函数注释中的字段列表
                    fields_comment_start = func_def.find('"""准备生产订单数据\n        按照数据库字段顺序:')
                    fields_comment_end = func_def.find('"""\n        ', fields_comment_start + 1)
                    
                    if fields_comment_start != -1 and fields_comment_end != -1:
                        # 提取字段注释
                        fields_comment = func_def[fields_comment_start:fields_comment_end + 4]
                        
                        # 更新字段注释
                        new_fields_comment = fields_comment
                        for field_name in NEW_FIELDS.keys():
                            if field_name.upper() not in new_fields_comment:
                                new_fields_comment = new_fields_comment.replace('"""\n        ', f", {field_name.upper()}\"\"\"\n        ")
                        
                        # 查找return语句
                        return_start = func_def.find("return (")
                        return_end = func_def.find(")\n", return_start)
                        
                        if return_start != -1 and return_end != -1:
                            # 提取返回值
                            return_values = func_def[return_start + len("return ("):return_end]
                            
                            # 添加新字段返回值
                            new_return_values = return_values
                            for field_name in NEW_FIELDS.keys():
                                api_field = field_name.upper()
                                if api_field not in new_return_values:
                                    new_return_values += f",\n                    item.get('{api_field}')"
                            
                            # 更新返回语句
                            new_func_def = func_def.replace(return_values, new_return_values)
                            new_func_def = new_func_def.replace(fields_comment, new_fields_comment)
                            
                            # 替换函数定义
                            new_content = new_content.replace(func_def, new_func_def)
                
                # 写入更新后的内容
                with open(mysql_manager_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                print("✅ 成功更新MySQL管理器中的SQL语句和数据准备函数")
                return True
            else:
                print("❌ 未找到字段定义部分，请手动更新MySQL管理器")
                return False
        except Exception as e:
            print(f"❌ 更新MySQL管理器失败: {str(e)}")
            return False
    
    def update_config_manager(self):
        """更新配置管理器中的字段配置"""
        try:
            # 读取config_manager.py文件
            config_manager_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'config', 'config_manager.py')
            with open(config_manager_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找生产订单字段配置
            field_keys_start = content.find('"生产订单": {\n')
            if field_keys_start != -1:
                field_keys_line_start = content.find('"FieldKeys":', field_keys_start)
                field_keys_line_end = content.find(',\n', field_keys_line_start)
                
                if field_keys_line_start != -1 and field_keys_line_end != -1:
                    # 提取FieldKeys值
                    field_keys_str = content[field_keys_line_start + len('"FieldKeys": '):field_keys_line_end]
                    
                    # 检查是否需要添加新字段
                    if 'FSTATUS' not in field_keys_str and 'FSTOCKINQUAQTY' not in field_keys_str:
                        # 去掉引号
                        field_keys_str = field_keys_str.strip('"')
                        
                        # 添加新字段
                        new_field_keys_str = field_keys_str + ',FSTATUS,FSTOCKINQUAQTY'
                        
                        # 更新FieldKeys
                        new_content = content[:field_keys_line_start + len('"FieldKeys": ')] + f'"{new_field_keys_str}"' + content[field_keys_line_end:]
                        
                        # 写入更新后的内容
                        with open(config_manager_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        
                        print("✅ 成功更新配置管理器中的字段配置")
                        return True
                    else:
                        print("ℹ️ 配置管理器中已包含新字段，无需更新")
                        return True
                else:
                    print("❌ 未找到FieldKeys配置，请手动更新配置管理器")
                    return False
            else:
                print("❌ 未找到生产订单配置，请手动更新配置管理器")
                return False
        except Exception as e:
            print(f"❌ 更新配置管理器失败: {str(e)}")
            return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="生产订单表字段添加工具")
    parser.add_argument("--skip-db", action="store_true", help="跳过数据库操作，只更新代码")
    parser.add_argument("--skip-code", action="store_true", help="跳过代码更新，只更新数据库")
    
    args = parser.parse_args()
    
    adder = ProductionOrderFieldAdder()
    
    # 更新数据库
    if not args.skip_db:
        if not adder.connect():
            return
        
        if not adder.check_table_exists():
            print(f"❌ 表 {adder.table_name} 不存在，请先创建表")
            adder.close()
            return
        
        # 添加字段
        for field_name, (data_type, is_null, default_value) in NEW_FIELDS.items():
            if not adder.check_field_exists(field_name):
                adder.add_field(field_name, data_type, is_null, default_value)
            else:
                print(f"ℹ️ 字段 {field_name} 已存在，跳过添加")
        
        adder.close()
    
    # 更新代码
    if not args.skip_code:
        adder.update_mysql_manager()
        adder.update_config_manager()
    
    print("✅ 操作完成")

if __name__ == "__main__":
    main()