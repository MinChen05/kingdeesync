"""
金蝶API连接和认证模块
负责与金蝶系统进行HTTP通信
"""
import requests
import time
import json
import logging
import threading
from typing import Dict, List, Any, Optional
from src.config.config_manager import config_manager
from src.core.retry_manager import retry_manager, RetryConfig, RetryStrategy

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

logger = logging.getLogger(__name__)

class KingdeeAPIClient:
    """金蝶API客户端"""
    
    def __init__(self):
        self.config = config_manager.get_kingdee_config()
        self._ssl_verify = str(self.config.get('ssl_verify', 'false')).lower() not in ('false', '0', 'no')
        self.session = requests.Session()
        self.session.verify = self._ssl_verify
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.is_authenticated = False
        self.session_id = None
        # 保持会话相关
        self._keepalive_thread: Optional[threading.Thread] = None
        self._keepalive_stop = threading.Event()
        # 控制查询期间暂停心跳
        self._pause_keepalive = threading.Event()
        # 限流初始化（QPS）
        try:
            qps = float(self.config.get('rate_limit_qps', 2.0))
            self._min_interval = (1.0 / qps) if qps > 0 else 0.0
        except Exception:
            self._min_interval = 0.0
        self._last_request_ts = 0.0
        self._throttle_lock = threading.Lock()

    def _throttle(self):
        """简单限流：控制最小请求间隔（线程安全）
        锁仅用于预留时间槽，sleep 在锁外执行，多线程可并发等待互不阻塞。
        """
        if self._min_interval <= 0:
            return
        with self._throttle_lock:
            now = time.time()
            wait = self._min_interval - (now - self._last_request_ts)
            if wait > 0:
                # 预留时间槽：将下次可用时间向后推，释放锁后再 sleep
                self._last_request_ts = now + wait
            else:
                wait = 0
                self._last_request_ts = now
        if wait > 0:
            time.sleep(wait)
    
    def login(self) -> bool:
        """登录金蝶系统"""
        # 每次登录前重置 Session 以确保干净的环境（清除旧Cookies和连接）
        self.session = requests.Session()
        self.session.verify = self._ssl_verify
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

        def _do_login():
            login_data = {
                "acctID": self.config['acct_id'],
                "username": self.config['username'],
                "password": self.config['password'],
                "lcid": self.config['lcid']
            }
            logger.info("正在登录金蝶系统...")
            response = self.session.post(
                self.config['login_url'],
                json=login_data,
                timeout=60
            )
            if response.status_code == 200:
                result = response.json()
                if result.get('LoginResultType') == 1:
                    self.is_authenticated = True
                    self.session_id = result.get('SessionId')
                    logger.info("金蝶系统登录成功")
                    try:
                        if self.config.get('keep_session_alive', False):
                            self._start_keepalive()
                    except Exception:
                        pass
                    return True
                else:
                    error_msg = result.get('Message', '登录失败')
                    logger.error(f"金蝶系统登录失败: {error_msg}")
                    # 业务层面登录失败（如密码错误），抛出 ValueError 以跳过重试
                    raise ValueError(f"业务登录失败: {error_msg}")
            else:
                logger.error(f"登录请求失败，状态码: {response.status_code}")
                raise requests.exceptions.HTTPError(f"HTTP {response.status_code}")

        try:
            result, _ = retry_manager.execute_with_retry(
                _do_login,
                "登录金蝶系统",
                "login"
            )
            return bool(result)
        except ValueError:
            # 业务层面登录失败（如密码错误），不重试
            return False
        except Exception as e:
            logger.error(f"登录金蝶系统失败: {str(e)}")
            return False

    def _keep_alive_ping(self):
        """发送轻量心跳请求以保持会话存活"""
        # 选用一个极轻量查询：请求0行或无条件但limit很小
        payload = {
            "data": {
                "FormId": "BD_MATERIAL",
                "FieldKeys": "FMATERIALID",
                "FilterString": "1=0",  # 始终返回空集
                "TopRowCount": 0,
                "StartRow": 0,
                "Limit": 10,   # 避免使用 Limit=1；实际返回0行（FilterString=1=0），无需大值
                "OrderString": "",
                "SubSystemId": ""
            }
        }
        try:
            self._throttle()
            # 心跳请求不设置超时（或很小），避免长时间阻塞退出流程
            resp = self.session.post(self.config['query_url'], json=payload, timeout=30)
            if resp.status_code == 200:
                # 尝试解析以确认是否需要重登录
                data = resp.json()
                if isinstance(data, dict):
                    rs = data.get('Result', {})
                    status = rs.get('ResponseStatus', {})
                    if not status.get('IsSuccess', True):
                        # 如果心跳失败，仅标记状态，不自动重登，避免干扰主线程
                        logger.warning("心跳检测表明会话已失效")
                        self.is_authenticated = False
            else:
                logger.warning(f"心跳请求状态码: {resp.status_code}")
        except Exception as e:
            logger.debug(f"心跳异常: {e}")

    def _keepalive_loop(self):
        interval = int(self.config.get('keep_alive_interval_secs', 600))
        # 下限5秒，上限1小时
        interval = max(5, min(interval, 3600))
        while not self._keepalive_stop.is_set():
            # 若处于暂停状态（如有正在进行的查询），则跳过心跳
            if not self._pause_keepalive.is_set() and self.is_authenticated:
                self._keep_alive_ping()
            # 等待间隔或直到被停止
            self._keepalive_stop.wait(interval)

    def _start_keepalive(self):
        """启动心跳线程"""
        try:
            if self._keepalive_thread and self._keepalive_thread.is_alive():
                return
            self._keepalive_stop.clear()
            self._keepalive_thread = threading.Thread(target=self._keepalive_loop, name="KingdeeKeepAlive", daemon=True)
            self._keepalive_thread.start()
            logger.info("会话心跳已启动")
        except Exception as e:
            logger.debug(f"启动会话心跳失败: {e}")

    def stop_keepalive(self):
        """停止心跳线程"""
        try:
            self._keepalive_stop.set()
            if self._keepalive_thread and self._keepalive_thread.is_alive():
                self._keepalive_thread.join(timeout=2)
            logger.info("会话心跳已停止")
        except Exception:
            pass
    
    @staticmethod
    def _is_report_form(form_id: str) -> bool:
        """判断是否为报表类表单（需走 GetSysReportData 接口）"""
        _REPORT_FORM_IDS = frozenset({'GL_RPT_AccountBalance'})
        return form_id in _REPORT_FORM_IDS

    @staticmethod
    def _build_report_payload(form_id: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """构建报表查询请求体（GetSysReportData 接口格式）"""
        data = request_data.copy()
        # 报表接口不支持 FilterString（会触发“无效的 JSON 基元”错误），移除之
        data.pop('FilterString', None)
        # GetSysReportData 要求 data 参数为 JSON 字符串，且需在最外层传递 formId
        return {"formId": form_id, "data": json.dumps(data)}

    @staticmethod
    def _build_query_payload(request_data: Dict[str, Any]) -> Dict[str, Any]:
        """构建普通单据查询请求体（ExecuteBillQuery 接口格式）"""
        return {"data": request_data}

    def query_data(self, form_id: str, query_params: Dict[str, Any], page_callback=None) -> Optional[List[Dict]]:
        """查询金蝶数据
        支持分页、重试与详细进度日志，避免大表查询超时。
        """
        if not self.is_authenticated:
            logger.warning("未登录，尝试重新登录...")
            if not self.login():
                return None
        
        try:
            logger.info(f"正在查询表单数据: {form_id}")

            # 添加调试日志，查看查询参数
            logger.debug(f"查询参数(初始): {json.dumps(query_params, ensure_ascii=False, indent=2)}")

            preferred_page_size = query_params.pop("__preferred_page_size__", None)
            try:
                configured_page_size = int(str(self.config.get("page_size", "20000")).strip())
            except Exception:
                configured_page_size = 20000
            if configured_page_size < 1000:
                configured_page_size = 1000
            if configured_page_size > 100000:
                configured_page_size = 100000

            # 分页设置：默认使用配置项；全量/完全同步可通过调用方传入更大的建议值
            page_size_default = configured_page_size
            if preferred_page_size is not None:
                try:
                    page_size_default = max(page_size_default, int(preferred_page_size))
                except Exception:
                    pass
            start_row = int(query_params.get('StartRow', 0) or 0)
            use_paging = True
            page_size = page_size_default
            
            # 针对大表强制启用分页并调整超时
            large_tables = ("生产订单明细", "生产订单主表", "生产用料清单", "生产用料清单主表", "生产用料清单明细表", "预测订单")
            target_size = None
            min_page_size = 1000
            if form_id in large_tables:
                target_size = page_size_default

                if not use_paging or page_size != target_size:
                    use_paging = True
                    page_size = target_size
                    logger.info(f"[{form_id}] 数据量较大，强制启用分页(PageSize={target_size})")

            if use_paging and page_size > 0 and page_size < min_page_size:
                page_size = min_page_size
            inferred_server_page_cap = 10000

            max_pages = int(self.config.get('max_pages', 100000))  # 安全上限，防止无限循环

            # 在长查询开始前暂停心跳，避免心跳超时触发重登
            self._pause_keepalive.set()

            # 超时与重试参数（支持禁用超时）
            # 当 request_timeout<=0 时，不传入 timeout 参数，表示无限等待（无超时限制）
            cfg_timeout = 0
            try:
                cfg_timeout = int(str(self.config.get('request_timeout', '0')).strip())
            except Exception:
                cfg_timeout = 0
            timeout_enabled = cfg_timeout > 0
            base_timeout = 60
            if form_id in large_tables:
                # 强制取消超时限制
                timeout_enabled = False
                logger.info(f"[{form_id}] 数据量较大，强制取消超时限制")
            
            # DIAGNOSTIC LOG
            logger.info(f"[{form_id}] Query Config: UsePaging={use_paging}, PageSize={page_size}, StartRow={start_row}, TimeoutEnabled={timeout_enabled}")

            if timeout_enabled and cfg_timeout > 0:
                # 若有明确配置，则以配置为初始超时
                base_timeout = cfg_timeout
            all_rows: List[Any] = []
            total_fetched = 0
            page_index = 0

            # 低效分页检测与自愈变量
            inefficient_paging_count = 0
            session_reset_tried = False
            
            while True:
                page_index += 1
                if page_index > max_pages:
                    logger.warning(f"[{form_id}] 分页次数达到安全上限({max_pages})，提前结束以避免死循环。当前StartRow={start_row}")
                    break

                # 更新当前页的查询参数（仅在启用分页时）
                if use_paging:
                    query_params['StartRow'] = start_row
                    query_params['Limit'] = page_size
                    # 移除 TopRowCount 以避免与 Limit 冲突（部分版本API存在此问题）
                    if 'TopRowCount' in query_params:
                        query_params.pop('TopRowCount')
                    # DIAGNOSTIC LOG
                    logger.info(f"[{form_id}] Page {page_index} Request: StartRow={start_row}, Limit={page_size}")

                # 动态调整查询URL与请求体：报表走 GetSysReportData，单据走 ExecuteBillQuery
                target_url = self.config['query_url']
                request_data = query_params.copy()
                real_form_id = query_params.get('FormId', '')

                if self._is_report_form(real_form_id):
                    target_url = target_url.replace('ExecuteBillQuery', 'GetSysReportData')
                    request_payload = self._build_report_payload(real_form_id, request_data)
                else:
                    request_payload = self._build_query_payload(request_data)
                
                timeout_secs = base_timeout

                def _do_request():
                    self._throttle()
                    if timeout_enabled:
                        return self.session.post(
                            target_url,
                            json=request_payload,
                            timeout=timeout_secs
                        )
                    return self.session.post(target_url, json=request_payload)

                def _on_retry(attempt, exc):
                    nonlocal timeout_secs
                    if isinstance(exc, requests.exceptions.ReadTimeout):
                        timeout_secs = min(timeout_secs * 2, 300)
                        logger.warning(
                            f"[{form_id}] 第{page_index}页查询超时，超时时间调整为 {timeout_secs}s (第{attempt}次重试)"
                        )

                response, _ = retry_manager.execute_with_retry(
                    _do_request,
                    f"第{page_index}页查询",
                    form_id,
                    on_retry=_on_retry,
                )

                if response.status_code != 200:
                    logger.error(f"查询请求失败，状态码: {response.status_code}")
                    return None

                result = response.json()
                # 解析返回的数据（兼容字典或直接列表）
                page_rows: List[Any] = []
                if isinstance(result, dict):
                    # 优先检查是否存在 Rows 列表（报表或特殊查询结构）
                    if 'Result' in result and isinstance(result['Result'], dict) and 'Rows' in result['Result']:
                        rs = result['Result']
                        page_rows = rs.get('Rows', []) or []
                    else:
                        rs = result.get('Result', {})
                        status = rs.get('ResponseStatus', {})
                        if not status.get('IsSuccess', True):
                            logger.error(f"查询失败: {status.get('Errors', [])}")
                            return None
                        page_rows = rs.get('Result', []) or []
                elif isinstance(result, list):
                    # 少数情况下直接返回列表
                    if len(result) > 0 and isinstance(result[0], dict) and 'Result' in result[0]:
                        status = result[0]['Result'].get('ResponseStatus', {})
                        if not status.get('IsSuccess', True):
                            logger.error(f"查询失败: {status.get('Errors', [])}")
                            return None
                        page_rows = result[0]['Result'].get('Result', []) or []
                    else:
                        page_rows = result
                else:
                    logger.error(f"未知的返回结构类型: {type(result)}")
                    return None

                # 统一尝试映射：如果数据是列表且配置了 FieldKeys，则转换为字典
                if page_rows and isinstance(page_rows[0], list):
                    field_keys_str = query_params.get('FieldKeys', '')
                    if field_keys_str:
                        keys = [k.strip() for k in field_keys_str.split(',') if k.strip()]
                        mapped_rows = []
                        for row_vals in page_rows:
                            # 使用 zip 自动对齐，多余的列会被忽略，缺少的列会丢失
                            # 这种方式比严格检查长度更宽容，适合报表类数据
                            mapped_rows.append(dict(zip(keys, row_vals)))
                        page_rows = mapped_rows


                # 统计与日志
                got_count = len(page_rows)
                
                if page_callback:
                    page_callback(page_rows)
                    # When using callback, we don't store in all_rows to save memory
                    # Just append an empty dict or None to keep length matching total count
                    # Or better: keep all_rows empty but return total_fetched later?
                    # Let's just track a total_count variable
                else:
                    all_rows.extend(page_rows)
                    
                total_fetched += got_count
                
                logger.info(
                    f"{form_id} 第{page_index}页: 本页获取 {got_count} 条, 累计获取 {total_fetched} 条"
                )
                
                # 检测低效分页与自愈
                if use_paging and got_count == 1 and page_size > 100:
                    inefficient_paging_count += 1
                    if inefficient_paging_count >= 5:
                        logger.warning(f"[{form_id}] 检测到低效分页({inefficient_paging_count}次)：请求Limit={page_size}但仅返回1条数据。")
                    
                    # 尝试自愈：如果是会话问题，重置会话 (仅尝试一次)
                    if inefficient_paging_count >= 5 and not session_reset_tried:
                        logger.warning(f"[{form_id}] 检测到持续低效分页，尝试重置会话以解除可能的服务器端限制...")
                        try:
                            # 强制登出并重登
                            self.logout(force=True)
                            if self.login():
                                session_reset_tried = True
                                inefficient_paging_count = 0
                                # 回滚当前页已追加的数据（仅在未使用 callback 时有效）
                                # got_count==1 在此分支中始终成立，但显式用变量以保持语义清晰
                                if not page_callback and len(all_rows) >= got_count:
                                    del all_rows[-got_count:]
                                    total_fetched -= got_count
                                logger.info(f"[{form_id}] 会话重置成功，重试当前页(StartRow={start_row})...")
                                continue
                            else:
                                logger.error(f"[{form_id}] 会话重置失败，继续使用当前状态")
                        except Exception as e:
                            logger.error(f"[{form_id}] 自愈尝试异常: {e}")
                elif use_paging and got_count > 1:
                    inefficient_paging_count = 0
                    session_reset_tried = False  # 如果恢复正常，允许未来再次触发自愈重置

                if use_paging and got_count < page_size:
                    if form_id in large_tables or got_count >= inferred_server_page_cap:
                        logger.debug(
                            f"{form_id} 返回条数小于请求页大小({got_count} < {page_size})，继续翻页"
                        )
                    else:
                        logger.info(
                            f"{form_id} 返回条数小于请求页大小({got_count} < {page_size})，判定为末页，结束分页"
                        )
                        break

                if use_paging and target_size and got_count == page_size and page_size < target_size:
                    page_size = min(target_size, page_size * 2)

                # 结束条件：未启用分页（单次请求）或本页无数据
                if not use_paging or got_count == 0:
                    break

                # 下一页：按实际返回条数移动偏移，避免因服务端上限导致停滞
                start_row += got_count

            return all_rows
            
        except requests.exceptions.Timeout as e:
            logger.error(f"查询请求超时: {str(e)}")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"查询连接失败: {str(e)}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"查询请求异常: {str(e)}")
            return None
        except ValueError as e:
            logger.error(f"查询响应解析失败: {str(e)}")
            return None
        finally:
            # 查询结束，恢复心跳
            self._pause_keepalive.clear()
    
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
    
    # 已移除生产用料清单查询方法
    
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
                # 已移除“生产用料清单”分支
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
        if self.is_authenticated:
            return True
        return self.login()
    
    def logout(self, force: bool = False):
        """登出"""
        # 若配置为不自动登出，仅停止心跳并保留会话（进程结束仍会释放资源）
        try:
            self.stop_keepalive()
        except Exception:
            pass
        
        if force or self.config.get('auto_logout_on_exit', False):
            self.is_authenticated = False
            self.session_id = None
            try:
                self.session.close()
            except Exception:
                pass
            logger.info("已登出金蝶系统")
        else:
            logger.info("按配置已跳过自动登出（保持已登录状态）")


# 全局金蝶API客户端实例
kingdee_client = KingdeeAPIClient()
