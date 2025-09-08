"""
金蝶API连接和认证模块
负责与金蝶系统进行HTTP通信
"""
import requests
import json
import logging
from typing import Dict, List, Any, Optional
from src.config.config_manager import config_manager

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KingdeeAPIClient:
    """金蝶API客户端"""
    
    def __init__(self):
        self.config = config_manager.get_kingdee_config()
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.is_authenticated = False
        self.session_id = None
    
    def login(self) -> bool:
        """登录金蝶系统"""
        try:
            login_data = {
                "acctID": self.config['acct_id'],
                "username": self.config['username'],
                "password": self.config['password'],
                "lcid": self.config['lcid']
            }
            
            headers = {
                'Content-Type': 'application/json; charset=utf-8',
                'Accept': 'application/json'
            }
            
            logger.info("正在登录金蝶系统...")
            response = self.session.post(
                self.config['login_url'],
                json=login_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('LoginResultType') == 1:  # 登录成功
                    self.is_authenticated = True
                    self.session_id = result.get('SessionId')
                    logger.info("金蝶系统登录成功")
                    return True
                else:
                    error_msg = result.get('Message', '登录失败')
                    logger.error(f"金蝶系统登录失败: {error_msg}")
                    return False
            else:
                logger.error(f"登录请求失败，状态码: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"登录请求异常: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"登录过程发生错误: {str(e)}")
            return False
    
    def query_data(self, form_id: str, query_params: Dict[str, Any]) -> Optional[List[Dict]]:
        """查询金蝶数据"""
        if not self.is_authenticated:
            logger.warning("未登录，尝试重新登录...")
            if not self.login():
                return None
        
        try:
            logger.info(f"正在查询表单数据: {form_id}")
            
            # 添加调试日志，查看查询参数
            logger.debug(f"查询参数: {json.dumps(query_params, ensure_ascii=False, indent=2)}")
            
            # 金蝶云星空 API 需要特定的请求格式
            headers = {
                'Content-Type': 'application/json; charset=utf-8',
                'Accept': 'application/json'
            }
            
            # 构造金蝶API期望的请求格式，包含data参数
            request_payload = {
                "data": query_params
            }
            
            response = self.session.post(
                self.config['query_url'],
                json=request_payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # 添加调试日志，查看返回结果的结构
                logger.debug(f"金蝶API返回结果类型: {type(result)}, 内容: {str(result)[:500]}...")
                
                # 处理不同的返回结构
                if isinstance(result, dict):
                    # 正常的字典结构
                    if result.get('Result', {}).get('ResponseStatus', {}).get('IsSuccess'):
                        data = result.get('Result', {}).get('Result', [])
                        logger.info(f"成功查询到 {len(data)} 条数据")
                        return data
                    else:
                        error_msg = result.get('Result', {}).get('ResponseStatus', {}).get('Errors', [])
                        logger.error(f"查询失败: {error_msg}")
                        return None
                elif isinstance(result, list):
                    # 直接返回列表的情况，需要检查是否是错误响应
                    if len(result) > 0 and isinstance(result[0], dict):
                        # 检查是否是错误响应
                        first_item = result[0]
                        if 'Result' in first_item and 'ResponseStatus' in first_item['Result']:
                            response_status = first_item['Result']['ResponseStatus']
                            if not response_status.get('IsSuccess', False):
                                error_msg = response_status.get('Errors', [])
                                logger.error(f"查询失败: {error_msg}")
                                return None
                    
                    logger.info(f"成功查询到 {len(result)} 条数据（直接列表格式）")
                    return result
                else:
                    logger.error(f"未知的返回结构类型: {type(result)}")
                    return None
            else:
                logger.error(f"查询请求失败，状态码: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"查询请求异常: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"查询过程发生错误: {str(e)}")
            return None
    
    def query_sales_order(self, filter_string: str = None) -> Optional[List[Dict]]:
        """查询销售订单"""
        query_params = config_manager.get_form_queries()["销售订单"].copy()
        if filter_string:
            query_params["FilterString"] = filter_string
        return self.query_data("销售订单", query_params)
    
    def query_sales_outstock(self, filter_string: str = None) -> Optional[List[Dict]]:
        """查询销售出库单"""
        query_params = config_manager.get_form_queries()["销售出库单"].copy()
        if filter_string:
            query_params["FilterString"] = filter_string
        return self.query_data("销售出库单", query_params)
    
    def query_forecast_order(self, filter_string: str = None) -> Optional[List[Dict]]:
        """查询预测订单"""
        query_params = config_manager.get_form_queries()["预测订单"].copy()
        if filter_string:
            query_params["FilterString"] = filter_string
        return self.query_data("预测订单", query_params)
    
    def query_production_order(self, filter_string: str = None) -> Optional[List[Dict]]:
        """查询生产订单"""
        query_params = config_manager.get_form_queries()["生产订单"].copy()
        if filter_string:
            query_params["FilterString"] = filter_string
        return self.query_data("生产订单", query_params)
    
    def query_production_ppbom(self, filter_string: str = None) -> Optional[List[Dict]]:
        """查询生产用料清单"""
        query_params = config_manager.get_form_queries()["生产用料清单"].copy()
        if filter_string:
            query_params["FilterString"] = filter_string
        return self.query_data("生产用料清单", query_params)
    
    def query_multiple_forms(self, form_names: List[str], custom_filters: Dict[str, str] = None) -> Dict[str, List[Dict]]:
        """查询多个表单数据"""
        results = {}
        
        for form_name in form_names:
            try:
                if form_name == "销售订单":
                    filter_string = None
                    if custom_filters and form_name in custom_filters:
                        filter_string = custom_filters[form_name]
                    data = self.query_sales_order(filter_string)
                elif form_name == "销售出库单":
                    filter_string = None
                    if custom_filters and form_name in custom_filters:
                        filter_string = custom_filters[form_name]
                    data = self.query_sales_outstock(filter_string)
                elif form_name == "预测订单":
                    filter_string = None
                    if custom_filters and form_name in custom_filters:
                        filter_string = custom_filters[form_name]
                    data = self.query_forecast_order(filter_string)
                elif form_name == "生产订单":
                    filter_string = None
                    if custom_filters and form_name in custom_filters:
                        filter_string = custom_filters[form_name]
                    data = self.query_production_order(filter_string)
                elif form_name == "生产用料清单":
                    filter_string = None
                    if custom_filters and form_name in custom_filters:
                        filter_string = custom_filters[form_name]
                    data = self.query_production_ppbom(filter_string)
                else:
                    logger.warning(f"未知的表单类型: {form_name}")
                    data = []
                
                if data is not None:
                    results[form_name] = data
                else:
                    results[form_name] = []
                    logger.warning(f"表单 {form_name} 查询失败或无数据")
                    
            except Exception as e:
                logger.error(f"查询表单 {form_name} 时发生错误: {str(e)}")
                results[form_name] = []
        
        return results
    
    def test_connection(self) -> bool:
        """测试连接"""
        return self.login()
    
    def logout(self):
        """登出"""
        self.is_authenticated = False
        self.session_id = None
        self.session.close()
        logger.info("已登出金蝶系统")


# 全局金蝶API客户端实例
kingdee_client = KingdeeAPIClient()