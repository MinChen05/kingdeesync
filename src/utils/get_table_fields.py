#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库表字段获取脚本
用于获取销售订单、销售出库单、预测订单、生产订单表的字段信息
"""

import json
from typing import Any, Dict, List

import pymysql

from src.config.config_manager import config_manager


class TableFieldsAnalyzer:
    """数据库表字段分析器"""
    
    def __init__(self):
        self.config = config_manager.get_mysql_config()
        self.connection = None
        self.cursor = None
        
        # 目标表名映射
        self.target_tables = {
            "销售订单": "saleorder",
            "销售出库单": "sal_outstock", 
            "预测订单": "pln_forecast",
            "生产订单": "prd_mo"
        }
    
    def connect(self) -> bool:
        """连接数据库"""
        try:
            self.connection = pymysql.connect(
                host=self.config['host'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database'],
                charset=self.config['charset'],
                port=int(self.config.get('port', 3306)),
                autocommit=True,
                cursorclass=pymysql.cursors.DictCursor
            )
            self.cursor = self.connection.cursor()
            print(f"✓ 成功连接到数据库: {self.config['database']}")
            return True
        except Exception as e:
            print(f"✗ 数据库连接失败: {str(e)}")
            return False
    
    def disconnect(self):
        """断开数据库连接"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
            print("✓ 数据库连接已关闭")
        except Exception as e:
            print(f"✗ 关闭数据库连接时发生错误: {str(e)}")
    
    def get_table_fields(self, table_name: str) -> List[Dict[str, Any]]:
        """获取表的字段信息"""
        try:
            # 查询表结构
            sql = f"DESCRIBE {table_name}"
            self.cursor.execute(sql)
            fields = self.cursor.fetchall()
            
            field_info = []
            for field in fields:
                field_info.append({
                    'field_name': field['Field'],
                    'data_type': field['Type'],
                    'is_null': field['Null'],
                    'key': field['Key'],
                    'default': field['Default'],
                    'extra': field['Extra']
                })
            
            return field_info
            
        except Exception as e:
            print(f"✗ 获取表 {table_name} 字段信息失败: {str(e)}")
            return []
    
    def check_table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        try:
            sql = f"SHOW TABLES LIKE '{table_name}'"
            self.cursor.execute(sql)
            result = self.cursor.fetchone()
            return result is not None
        except Exception as e:
            print(f"✗ 检查表 {table_name} 是否存在时发生错误: {str(e)}")
            return False
    
    def analyze_all_tables(self) -> Dict[str, Any]:
        """分析所有目标表的字段信息"""
        if not self.connect():
            return {}
        
        analysis_result = {
            'database': self.config['database'],
            'analysis_time': None,
            'tables': {}
        }
        
        try:
            from datetime import datetime
            analysis_result['analysis_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            for table_desc, table_name in self.target_tables.items():
                print(f"\n正在分析表: {table_desc} ({table_name})")
                
                # 检查表是否存在
                if not self.check_table_exists(table_name):
                    print(f"✗ 表 {table_name} 不存在")
                    analysis_result['tables'][table_desc] = {
                        'table_name': table_name,
                        'exists': False,
                        'fields': [],
                        'error': f"表 {table_name} 不存在"
                    }
                    continue
                
                # 获取字段信息
                fields = self.get_table_fields(table_name)
                if fields:
                    print(f"✓ 成功获取 {len(fields)} 个字段")
                    analysis_result['tables'][table_desc] = {
                        'table_name': table_name,
                        'exists': True,
                        'field_count': len(fields),
                        'fields': fields
                    }
                    
                    # 打印字段信息
                    print("字段列表:")
                    for i, field in enumerate(fields, 1):
                        print(f"  {i:2d}. {field['field_name']:25} {field['data_type']:20} {field['is_null']:5} {field['key']:5}")
                else:
                    analysis_result['tables'][table_desc] = {
                        'table_name': table_name,
                        'exists': True,
                        'fields': [],
                        'error': "获取字段信息失败"
                    }
            
            return analysis_result
            
        finally:
            self.disconnect()
    
    def save_analysis_result(self, result: Dict[str, Any], filename: str = "table_fields_analysis.json"):
        """保存分析结果到JSON文件"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n✓ 分析结果已保存到: {filename}")
        except Exception as e:
            print(f"\n✗ 保存分析结果失败: {str(e)}")
    
    def generate_insert_sql_template(self, result: Dict[str, Any]):
        """生成INSERT SQL模板"""
        print("\n" + "="*80)
        print("INSERT SQL 模板生成")
        print("="*80)
        
        for table_desc, table_info in result['tables'].items():
            if not table_info.get('exists', False) or not table_info.get('fields'):
                continue
                
            table_name = table_info['table_name']
            fields = table_info['fields']
            
            # 过滤掉自增字段和时间戳字段
            insert_fields = []
            for field in fields:
                if field['extra'].upper() != 'AUTO_INCREMENT' and field['field_name'] not in ['sync_time']:
                    insert_fields.append(field['field_name'])
            
            print(f"\n{table_desc} ({table_name}):")
            print(f"INSERT INTO {table_name} (")
            print("    " + ",\n    ".join(insert_fields))
            print(") VALUES (")
            print("    " + ", ".join(["%s"] * len(insert_fields)))
            print(")")
            
            print(f"\n字段顺序 ({len(insert_fields)} 个字段):")
            for i, field_name in enumerate(insert_fields, 1):
                field_info = next((f for f in fields if f['field_name'] == field_name), {})
                print(f"  {i:2d}. {field_name:25} {field_info.get('data_type', ''):20}")

def main():
    """主函数"""
    print("数据库表字段分析工具")
    print("="*50)
    
    analyzer = TableFieldsAnalyzer()
    
    # 分析所有表
    result = analyzer.analyze_all_tables()
    
    if result:
        # 保存分析结果
        analyzer.save_analysis_result(result)
        
        # 生成INSERT SQL模板
        analyzer.generate_insert_sql_template(result)
        
        print("\n" + "="*80)
        print("分析完成！")
        print("请查看 table_fields_analysis.json 文件获取详细信息")
        print("="*80)
    else:
        print("\n✗ 分析失败，请检查数据库连接配置")

if __name__ == "__main__":
    main()
