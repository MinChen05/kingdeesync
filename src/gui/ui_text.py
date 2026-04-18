"""
Shared UI copy tokens.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StateCopy:
    title: str
    desc: str


class ButtonText:
    """Common button labels."""

    SAVE = "保存"
    SAVE_CONFIG = "保存配置"
    SAVE_SETTINGS = "保存设置"
    TEST_CONNECTION = "测试连接"
    EXPORT = "导出"
    COPY = "复制"
    CLEAR = "清空"
    QUERY = "查询"
    REFRESH_DATA = "刷新数据"
    START_SYNC = "开始同步"
    START_TASK = "启动任务"
    STOP_TASK = "停止任务"


class LoadingText:
    """Loading-state labels."""

    DEFAULT = "处理中..."
    SAVE = "保存中..."
    TEST = "测试中..."
    EXPORT = "导出中..."
    COPY = "复制中..."
    CLEAR = "清空中..."
    REFRESH = "刷新中..."
    SYNC = "同步中..."
    START = "启动中..."
    STOP = "停止中..."


class StateText:
    """Empty / loading / error copy."""

    GENERIC_LOADING = StateCopy("加载中", "正在获取最新数据，请稍候。")
    GENERIC_LOAD_ERROR = StateCopy("加载失败", "请检查服务状态，或稍后重试。")

    HISTORY_EMPTY = StateCopy("暂无历史记录", "请调整筛选条件，或等待新的同步任务生成数据。")
    HISTORY_LOAD_ERROR = StateCopy("加载失败", "历史记录加载失败，请检查服务状态或稍后重试。")

    SYNC_LOG_EMPTY = StateCopy("暂无执行日志", "发起同步任务后，可在此查看实时执行信息。")
    SCHEDULE_LOG_EMPTY = StateCopy("暂无运行日志", "启动调度任务后，可在此查看任务执行日志。")

    DASHBOARD_ERROR_LOADING = StateCopy("加载中", "正在获取最近失败记录，请稍候。")
    DASHBOARD_ERROR_EMPTY = StateCopy("最近没有异常记录", "当前运行状态稳定，暂未发现需要处理的失败任务。")
    DASHBOARD_ERROR_FAILED = StateCopy("加载失败", "请检查历史服务状态，或稍后重试。")


class MessageText:
    """Feedback and dialog copy."""

    SAVE_SUCCESS = "保存成功"
    COPY_SUCCESS = "复制成功"
    EXPORT_SUCCESS = "导出成功"
    TEST_RESULT = "测试结果"
    TEST_FAILED = "测试失败"
    EXPORT_FAILED = "导出失败"
    COPY_EMPTY_TITLE = "暂无可复制内容"
    EXPORT_EMPTY_TITLE = "暂无可导出内容"
    LOG_EMPTY_TITLE = "暂无日志"

    CONFIG_SAVED = "配置已保存。"
    FORM_CONFIG_SAVED = "表单配置已保存。"
    SETTINGS_SAVED = "设置已保存。"
    SCHEDULE_SAVED = "调度配置已保存。"
    LOG_COPIED = "日志已复制到剪贴板。"
    DATA_COPIED = "数据已复制到剪贴板。"
    LOG_COPY_EMPTY = "当前没有可复制的日志内容。"
    DATA_EXPORT_EMPTY = "当前没有可导出的历史数据。"
    LOG_EXPORT_EMPTY = "当前没有可导出的日志内容。"


class ShellText:
    """Shared shell-level copy (Win11 main window chrome)."""

    SEARCH = "搜索"
    HISTORY = "历史记录"
    SYSTEM_SETTINGS = "系统设置"

    TOPBAR_SEARCH_PLACEHOLDER = "搜索页面、功能或关键字"
    TOPBAR_USER_BADGE = "金"
