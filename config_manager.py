"""
配置管理模块
负责管理金蝶API和MySQL数据库的配置信息
"""
import json
import configparser
import os
from typing import Dict, Any

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = "config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file, encoding='utf-8')
        else:
            self.create_default_config()
    
    def create_default_config(self):
        """创建默认配置文件"""
        # 金蝶API配置
        self.config['KINGDEE'] = {
            'login_url': 'https://jyxing.ik3cloud.com/k3cloud/Kingdee.BOS.WebApi.ServicesStub.AuthService.ValidateUser.common.kdsvc',
            'query_url': 'https://jyxing.ik3cloud.com/k3cloud/Kingdee.BOS.WebApi.ServicesStub.DynamicFormService.ExecuteBillQuery.common.kdsvc',
            'acct_id': '20211115163118805',
            'username': 'aps',
            'password': 'jy@123456',
            'lcid': '2052'
        }
        
        # MySQL数据库配置
        self.config['MYSQL'] = {
            'host': '192.169.0.32',
            'user': 'root',
            'password': '123456',
            'database': 'kingdee',
            'charset': 'utf8mb4',
            'port': '3306'
        }
        
        # 同步配置
        self.config['SYNC'] = {
            'auto_sync': 'False',
            'sync_interval': '60',  # 分钟
            'last_sync_time': '',
            'sync_type': 'incremental'  # incremental, full, complete
        }
        
        # GUI配置
        self.config['GUI'] = {
            'theme': 'blue',
            'window_width': '1200',
            'window_height': '800'
        }
        
        self.save_config()
    
    def save_config(self):
        """保存配置文件"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            self.config.write(f)
    
    def get_kingdee_config(self) -> Dict[str, str]:
        """获取金蝶配置"""
        return dict(self.config['KINGDEE'])
    
    def get_mysql_config(self) -> Dict[str, str]:
        """获取MySQL配置"""
        return dict(self.config['MYSQL'])
    
    def get_sync_config(self) -> Dict[str, Any]:
        """获取同步配置"""
        sync_config = dict(self.config['SYNC'])
        sync_config['auto_sync'] = sync_config['auto_sync'].lower() == 'true'
        sync_config['sync_interval'] = int(sync_config['sync_interval'])
        return sync_config
    
    def get_gui_config(self) -> Dict[str, Any]:
        """获取GUI配置"""
        gui_config = dict(self.config['GUI'])
        gui_config['window_width'] = int(gui_config['window_width'])
        gui_config['window_height'] = int(gui_config['window_height'])
        return gui_config
    
    def update_config(self, section: str, key: str, value: str):
        """更新配置"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = str(value)
        self.save_config()
    
    def get_form_queries(self) -> Dict[str, Dict]:
        """获取表单查询配置"""
        return {
            "销售订单": {
                "FormId": "SAL_SaleOrder",
                "FieldKeys": "FSaleOrderEntry_FENTRYID,FSaleOrderEntry_FSEQ,FBillTypeID.FName,FBillNo,FDate,FCustId.FName,FSaleOrgId.FName,FCustId.FGROUP,FMaterialId.FName,FMaterialId.FNumber,FMaterialId.F_ora_Text_qtr,FMaterialId.FBarcode,FQTY,FCloseStatus,FDeliveryDate,FModifyDate",
                "FilterString": "FDocumentStatus='c' and FSaleOrgId = 171190 and FBillTypeID.FName='标准销售订单' and FMaterialId.FName='电机'",
                "OrderString": "",
                "TopRowCount": 0,
                "StartRow": 0,
                "Limit": 0,
                "SubSystemId": ""
            },
            "销售出库单": {
                "FormId": "SAL_OUTSTOCK",
                "FieldKeys": "FEntity_FENTRYID,FBillTypeID.FName,FBillNO,FDate,FCustomerID.FNAME,FSaleOrgId.FNAME,FCustomerID.FGROUP,FRealQty,FMaterialID.FNAME,FMaterialID.FNUMBER,FMaterialID.F_ora_Text_qtr,FMaterialID.FBarcode,FModifyDate",
                "FilterString": "FDocumentStatus='c' and FSaleOrgId=171190 and FBillTypeID.FName='标准销售出库单' and FMaterialID.FNAME='电机'",
                "OrderString": "",
                "TopRowCount": 0,
                "StartRow": 0,
                "Limit": 0,
                "SubSystemId": ""
            },
            "预测订单": {
                "FormId": "PLN_FORECAST",
                "FieldKeys": "FEntity_FENTRYID,FBillNo,FForeOrgId.FNAME,FCustId.FNAME,FMaterialId.FNAME,FMaterialId.FNUMBER,FQty,F_ora_Base.FNAME,F_ora_BaseProperty_ca9,F_ora_BaseProperty_uky,F_ora_Date,FModifyDate",
                "FilterString": "FDocumentStatus='c' and FForeOrgId = '171190' and FMaterialId.FName='电机'",
                "OrderString": "",
                "TopRowCount": 0,
                "StartRow": 0,
                "Limit": 0,
                "SubSystemId": ""
            }
        }


# 全局配置管理器实例
config_manager = ConfigManager()