"""
配置验证模块
启动时验证表单映射、字段完整性和连接状态
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """验证状态"""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ValidationResult:
    """验证结果"""

    check_name: str
    status: ValidationStatus
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
        }


class ConfigValidator:
    """配置验证器"""

    # 必需的配置节
    REQUIRED_SECTIONS = ["KINGDEE", "SQLSERVER", "SYNC"]

    # 必需的金蝶API配置项
    REQUIRED_KINGDEE_KEYS = ["login_url", "query_url", "acct_id", "username", "password"]

    # 必需的数据库配置项
    REQUIRED_DB_KEYS = ["host", "database", "user", "password"]

    # 必需的同步配置项
    REQUIRED_SYNC_KEYS = ["sync_type"]

    # 预期的表单字段映射（关键字段）
    EXPECTED_FORM_FIELDS = {
        "销售订单": ["FID", "FBillNo", "FCustId", "FMaterialId"],
        "销售出库单": ["FID", "FBillNo", "FCustId", "FMaterialId"],
        "销售退货单": ["FID", "FBillNo", "FCustId", "FMaterialId"],
        "预测订单": ["FID", "FBillNo", "FCustId", "FMaterialId"],
        "发货通知单": ["FID", "FBillNo", "FCustId", "FMaterialId"],
        "生产入库单": ["FID", "FBillNo", "FMaterialId"],
        "生产订单主表": ["FID", "FBillNo", "FMaterialId"],
        "生产订单明细": ["FENTRYID", "FID", "FMaterialId"],
        "客户资料": ["FCUSTID", "FNUMBER", "FNAME"],
        "生产用料清单主表": ["FID", "FBillNo", "FMaterialId"],
        "生产用料清单明细表": ["FENTRYID", "FID", "FMaterialId"],
        "即时库存": ["FSTOCKID", "FMaterialId", "FQty"],
        "物料": ["FMATERIALID", "FNUMBER", "FNAME"],
        "物料清单": ["FID", "FNUMBER", "FNAME"],
        "物料清单子项": ["FENTRYID", "FID", "FMaterialId"],
        "仓库": ["FSTOCKID", "FNUMBER", "FNAME"],
        "采购订单": ["FID", "FBillNo", "FSupplierId", "FMaterialId"],
        "委外订单": ["FID", "FBillNo", "FSupplierId", "FMaterialId"],
        "科目余额表": ["FACCTID", "FACCTNAME"],
    }

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.results: List[ValidationResult] = []

    def validate_all(self) -> Tuple[bool, List[ValidationResult]]:
        """执行所有验证"""
        self.results = []

        # 1. 验证配置文件
        self._validate_config_file()

        # 2. 验证配置节
        self._validate_sections()

        # 3. 验证金蝶API配置
        self._validate_kingdee_config()

        # 4. 验证数据库配置
        self._validate_db_config()

        # 5. 验证同步配置
        self._validate_sync_config()

        # 6. 验证表单映射
        self._validate_table_mapping()

        # 7. 验证表单查询配置
        self._validate_form_queries()

        # 汇总结果
        has_failure = any(r.status == ValidationStatus.FAILED for r in self.results)
        return not has_failure, self.results

    def _add_result(self, check_name: str, status: ValidationStatus, message: str, details: Optional[Dict] = None):
        """添加验证结果"""
        self.results.append(ValidationResult(check_name, status, message, details))
        if status == ValidationStatus.FAILED:
            logger.error(f"验证失败 [{check_name}]: {message}")
        elif status == ValidationStatus.WARNING:
            logger.warning(f"验证警告 [{check_name}]: {message}")
        else:
            logger.info(f"验证通过 [{check_name}]: {message}")

    def _validate_config_file(self):
        """验证配置文件是否存在"""
        import os

        config_file = self.config_manager.config_file

        if os.path.exists(config_file):
            self._add_result("配置文件", ValidationStatus.PASSED, f"配置文件存在: {config_file}")
        else:
            self._add_result("配置文件", ValidationStatus.WARNING, f"配置文件不存在，将使用默认配置: {config_file}")

    def _validate_sections(self):
        """验证配置节"""
        config = self.config_manager.config
        missing_sections = []

        for section in self.REQUIRED_SECTIONS:
            if not config.has_section(section):
                missing_sections.append(section)

        if missing_sections:
            self._add_result(
                "配置节",
                ValidationStatus.WARNING,
                f"缺少配置节: {', '.join(missing_sections)} (将使用默认值)",
                {"missing": missing_sections},
            )
        else:
            self._add_result("配置节", ValidationStatus.PASSED, "所有必需配置节已存在")

    def _validate_kingdee_config(self):
        """验证金蝶API配置"""
        try:
            kingdee_config = self.config_manager.get_kingdee_config()
            missing_keys = []

            for key in self.REQUIRED_KINGDEE_KEYS:
                if key not in kingdee_config or not kingdee_config[key]:
                    missing_keys.append(key)

            if missing_keys:
                # password可以是加密的，单独检查
                if "password" in missing_keys:
                    pwd = kingdee_config.get("password", "")
                    if pwd and pwd.startswith("encrypted:"):
                        missing_keys.remove("password")

            if missing_keys:
                self._add_result(
                    "金蝶API配置",
                    ValidationStatus.FAILED,
                    f"金蝶API配置不完整，缺少: {', '.join(missing_keys)}",
                    {"missing_keys": missing_keys},
                )
            else:
                # 验证URL格式
                login_url = kingdee_config.get("login_url", "")
                query_url = kingdee_config.get("query_url", "")

                url_warnings = []
                if not login_url.startswith("http"):
                    url_warnings.append("login_url格式异常")
                if not query_url.startswith("http"):
                    url_warnings.append("query_url格式异常")

                if url_warnings:
                    self._add_result(
                        "金蝶API配置",
                        ValidationStatus.WARNING,
                        f"配置警告: {', '.join(url_warnings)}",
                        {"warnings": url_warnings},
                    )
                else:
                    self._add_result(
                        "金蝶API配置",
                        ValidationStatus.PASSED,
                        f"金蝶API配置完整 (账户: {kingdee_config.get('acct_id', 'N/A')})",
                    )

        except Exception as e:
            self._add_result("金蝶API配置", ValidationStatus.FAILED, f"获取金蝶配置失败: {str(e)}")

    def _validate_db_config(self):
        """验证数据库配置"""
        try:
            db_config = self.config_manager.get_db_config()
            sqlserver_config = db_config.get("sqlserver", {})
            missing_keys = []

            for key in self.REQUIRED_DB_KEYS:
                if key not in sqlserver_config or not sqlserver_config[key]:
                    missing_keys.append(key)

            # password可以是加密的
            if "password" in missing_keys:
                pwd = sqlserver_config.get("password", "")
                if pwd and pwd.startswith("encrypted:"):
                    missing_keys.remove("password")

            if missing_keys:
                self._add_result(
                    "数据库配置",
                    ValidationStatus.FAILED,
                    f"数据库配置不完整，缺少: {', '.join(missing_keys)}",
                    {"missing_keys": missing_keys},
                )
            else:
                host = sqlserver_config.get("host", "N/A")
                database = sqlserver_config.get("database", "N/A")
                self._add_result("数据库配置", ValidationStatus.PASSED, f"数据库配置完整 ({host}/{database})")

        except Exception as e:
            self._add_result("数据库配置", ValidationStatus.FAILED, f"获取数据库配置失败: {str(e)}")

    def _validate_sync_config(self):
        """验证同步配置"""
        try:
            sync_config = self.config_manager.get_sync_config()
            missing_keys = []

            for key in self.REQUIRED_SYNC_KEYS:
                if key not in sync_config or not sync_config[key]:
                    missing_keys.append(key)

            if missing_keys:
                self._add_result(
                    "同步配置",
                    ValidationStatus.WARNING,
                    f"同步配置不完整，缺少: {', '.join(missing_keys)} (将使用默认值)",
                    {"missing_keys": missing_keys},
                )
            else:
                sync_type = sync_config.get("sync_type", "N/A")
                self._add_result("同步配置", ValidationStatus.PASSED, f"同步配置完整 (默认模式: {sync_type})")

        except Exception as e:
            self._add_result("同步配置", ValidationStatus.WARNING, f"获取同步配置失败: {str(e)}")

    def _validate_table_mapping(self):
        """验证表单映射"""
        try:
            table_mapping = self.config_manager.get_table_mapping()

            if not table_mapping:
                self._add_result("表单映射", ValidationStatus.FAILED, "表单映射为空")
                return

            # 检查映射完整性
            empty_mappings = [k for k, v in table_mapping.items() if not v]

            if empty_mappings:
                self._add_result(
                    "表单映射",
                    ValidationStatus.WARNING,
                    f"以下表单映射为空: {', '.join(empty_mappings)}",
                    {"empty_mappings": empty_mappings},
                )
            else:
                self._add_result("表单映射", ValidationStatus.PASSED, f"共 {len(table_mapping)} 个表单映射已配置")

        except Exception as e:
            self._add_result("表单映射", ValidationStatus.FAILED, f"获取表单映射失败: {str(e)}")

    def _validate_form_queries(self):
        """验证表单查询配置"""
        try:
            form_queries = self.config_manager.get_form_queries()

            if not form_queries:
                self._add_result("表单查询配置", ValidationStatus.WARNING, "表单查询配置为空")
                return

            missing_field_keys = []
            missing_form_id = []

            for form_name, query_config in form_queries.items():
                if not query_config.get("FieldKeys"):
                    missing_field_keys.append(form_name)
                if not query_config.get("FormId"):
                    missing_form_id.append(form_name)

            issues = []
            if missing_field_keys:
                issues.append(f"缺少FieldKeys: {len(missing_field_keys)}个")
            if missing_form_id:
                issues.append(f"缺少FormId: {len(missing_form_id)}个")

            if issues:
                self._add_result(
                    "表单查询配置",
                    ValidationStatus.WARNING,
                    f"表单查询配置存在警告: {', '.join(issues)}",
                    {
                        "missing_field_keys": missing_field_keys,
                        "missing_form_id": missing_form_id,
                    },
                )
            else:
                self._add_result("表单查询配置", ValidationStatus.PASSED, f"共 {len(form_queries)} 个表单查询配置完整")

        except Exception as e:
            self._add_result("表单查询配置", ValidationStatus.WARNING, f"获取表单查询配置失败: {str(e)}")

    def get_summary(self) -> str:
        """获取验证摘要"""
        passed = sum(1 for r in self.results if r.status == ValidationStatus.PASSED)
        warnings = sum(1 for r in self.results if r.status == ValidationStatus.WARNING)
        failed = sum(1 for r in self.results if r.status == ValidationStatus.FAILED)

        lines = [
            "=" * 50,
            "配置验证摘要",
            "=" * 50,
            f"通过: {passed}",
            f"警告: {warnings}",
            f"失败: {failed}",
            "-" * 50,
        ]

        for result in self.results:
            status_symbol = {
                ValidationStatus.PASSED: "✓",
                ValidationStatus.WARNING: "⚠",
                ValidationStatus.FAILED: "✗",
            }.get(result.status, "?")

            lines.append(f"{status_symbol} {result.check_name}: {result.message}")

        lines.append("=" * 50)
        return "\n".join(lines)


def validate_config(config_manager) -> Tuple[bool, List[ValidationResult]]:
    """验证配置的便捷函数"""
    validator = ConfigValidator(config_manager)
    return validator.validate_all()
