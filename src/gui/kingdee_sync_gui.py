"""
GUI主界面模块 - 第一部分
使用PySide6创建Windows 11风格的蓝色主题界面
"""
import sys
import os
from datetime import datetime
from typing import List, Dict

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QGroupBox, QLabel, QPushButton, QCheckBox, QComboBox,
    QSpinBox, QTextEdit, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QSplitter, QScrollArea, QMessageBox,
    QSystemTrayIcon, QMenu, QStatusBar
)
from PySide6.QtCore import (
    Qt, QTimer, QThread, Signal, QSize, QPropertyAnimation, QRect
)
from PySide6.QtGui import (
    QFont, QPalette, QColor, QIcon, QPixmap, QPainter, QBrush, QTextCursor
)

from src.core.data_sync import sync_manager, SyncType
from src.core.scheduler import auto_scheduler, SchedulerStatus
from src.config.config_manager import config_manager

class SyncWorker(QThread):
    """同步工作线程"""
    progress = Signal(str, int)
    finished = Signal(dict)
    
    def __init__(self, forms: List[str], sync_type: SyncType):
        super().__init__()
        self.forms = forms
        self.sync_type = sync_type
    
    def run(self):
        """执行同步任务"""
        try:
            sync_manager.add_sync_callback(self._on_progress)
            result = sync_manager.sync_data(self.forms, self.sync_type)
            self.finished.emit(result)
        except Exception as e:
            error_result = {
                'status': 'failed',
                'message': f'同步异常: {str(e)}',
                'total_records': 0,
                'details': {}
            }
            self.finished.emit(error_result)
    
    def _on_progress(self, message: str, progress: int):
        """进度回调"""
        self.progress.emit(message, progress)

class KingdeeSyncGUI(QMainWindow):
    """金蝶数据同步工具主界面"""
    
    def __init__(self):
        super().__init__()
        self.sync_worker = None
        self.init_ui()
        self.setup_connections()
        self.setup_timer()
        self.apply_theme()
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("金蝶数据同步工具 v1.0")
        self.setGeometry(100, 100, 1400, 900)  # 增大窗口尺寸
        self.setMinimumSize(1200, 800)  # 设置最小尺寸
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局和侧边栏
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建左侧侧边栏
        self.create_sidebar(main_layout)
        
        # 创建右侧主内容区域
        self.create_main_content(main_layout)
        
        self.create_status_bar()
    
    def create_sidebar(self, main_layout):
        """创建左侧侧边栏"""
        sidebar_frame = QFrame()
        sidebar_frame.setFixedWidth(280)
        sidebar_frame.setFrameStyle(QFrame.StyledPanel)
        sidebar_frame.setObjectName("sidebar")
        
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setSpacing(15)
        sidebar_layout.setContentsMargins(15, 20, 15, 20)
        
        # 标题
        title_label = QLabel("金蝶数据同步")
        title_label.setObjectName("sidebar-title")
        sidebar_layout.addWidget(title_label)
        
        # 快速状态卡片
        self.create_status_cards(sidebar_layout)
        
        # 快速操作按钮
        self.create_quick_actions(sidebar_layout)
        
        # 连接状态区域
        self.create_connection_status(sidebar_layout)
        
        sidebar_layout.addStretch()
        main_layout.addWidget(sidebar_frame)
    
    def create_status_cards(self, layout):
        """创建状态卡片"""
        # 今日同步次数卡片
        sync_card = self.create_info_card("今日同步", "0 次", "#4CAF50")
        layout.addWidget(sync_card)
        
        # 数据总量卡片
        data_card = self.create_info_card("数据总量", "0 条", "#2196F3")
        layout.addWidget(data_card)
        
        # 运行状态卡片
        self.status_card = self.create_info_card("运行状态", "已停止", "#FF9800")
        layout.addWidget(self.status_card)
    
    def create_info_card(self, title, value, color):
        """创建信息卡片"""
        card = QFrame()
        card.setObjectName("info-card")
        card.setFixedHeight(80)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(15, 10, 15, 10)
        
        title_label = QLabel(title)
        title_label.setObjectName("card-title")
        
        value_label = QLabel(value)
        value_label.setObjectName("card-value")
        value_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 18px;")
        
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        
        return card
    
    def create_quick_actions(self, layout):
        """创建快速操作按钮"""
        actions_label = QLabel("快速操作")
        actions_label.setObjectName("section-title")
        layout.addWidget(actions_label)
        
        # 手动同步按钮
        self.quick_sync_btn = QPushButton("🔄 立即同步")
        self.quick_sync_btn.setObjectName("quick-action-btn")
        self.quick_sync_btn.setMinimumHeight(45)
        self.quick_sync_btn.clicked.connect(self.quick_sync)
        layout.addWidget(self.quick_sync_btn)
        
        # 测试连接按钮
        self.quick_test_btn = QPushButton("🔌 测试连接")
        self.quick_test_btn.setObjectName("quick-action-btn")
        self.quick_test_btn.setMinimumHeight(45)
        self.quick_test_btn.clicked.connect(self.test_connections)
        layout.addWidget(self.quick_test_btn)
        
        # 数据验证按钮
        self.quick_validate_btn = QPushButton("✓ 数据验证")
        self.quick_validate_btn.setObjectName("quick-action-btn")
        self.quick_validate_btn.setMinimumHeight(45)
        self.quick_validate_btn.clicked.connect(self.validate_data)
        layout.addWidget(self.quick_validate_btn)
    
    def create_connection_status(self, layout):
        """创建连接状态区域"""
        conn_label = QLabel("连接状态")
        conn_label.setObjectName("section-title")
        layout.addWidget(conn_label)
        
        # 金蝶API状态
        self.kingdee_status = QLabel("🔴 金蝶API: 未连接")
        self.kingdee_status.setObjectName("status-label")
        layout.addWidget(self.kingdee_status)
        
        # MySQL状态
        self.mysql_status = QLabel("🔴 MySQL: 未连接")
        self.mysql_status.setObjectName("status-label")
        layout.addWidget(self.mysql_status)
    
    def create_main_content(self, main_layout):
        """创建主内容区域"""
        content_frame = QFrame()
        content_frame.setObjectName("main-content")
        
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("main-tabs")
        
        self.create_sync_tab()
        self.create_schedule_tab()
        self.create_history_tab()
        self.create_settings_tab()
        
        content_layout.addWidget(self.tab_widget)
        main_layout.addWidget(content_frame)
    
    def create_sync_tab(self):
        """创建同步标签页"""
        sync_widget = QWidget()
        layout = QHBoxLayout(sync_widget)  # 使用水平布局
        layout.setSpacing(20)
        
        # 左侧配置区域
        left_panel = QWidget()
        left_panel.setFixedWidth(400)
        left_layout = QVBoxLayout(left_panel)
        
        # 表单选择区域 - 改为下拉选择框
        form_group = QGroupBox("📄 选择同步表单")
        form_layout = QVBoxLayout(form_group)
        
        # 创建下拉选择框
        self.form_selector = QComboBox()
        self.form_selector.setMinimumHeight(40)
        self.form_selector.addItems([
            "同步所有表单",
            "销售订单", 
            "销售出库单", 
            "预测订单",
            "生产订单",
            "生产用料清单",
            "自定义选择..."
        ])
        
        # 设置默认选择
        self.form_selector.setCurrentText("同步所有表单")
        
        # 添加说明文本
        form_desc = QLabel("""• 同步所有表单: 一次性同步所有业务数据
• 单独选择: 只同步指定的业务表单
• 自定义选择: 打开多选对话框进行精确控制""")
        form_desc.setObjectName("form-description")
        
        form_layout.addWidget(self.form_selector)
        form_layout.addWidget(form_desc)
        
        # 保留原有的复选框结构（隐藏，用于自定义选择）
        self.form_checkboxes = {}
        self.custom_form_frame = QFrame()
        self.custom_form_frame.setVisible(False)  # 默认隐藏
        custom_layout = QVBoxLayout(self.custom_form_frame)
        
        forms_info = [
            ("销售订单", "📊 销售订单数据"),
            ("销售出库单", "📦 销售出库单数据"),
            ("预测订单", "🔮 预测订单数据"),
            ("生产订单", "🏭 生产订单数据"),
            ("生产用料清单", "🧰 生产用料清单数据")
        ]
        
        for form_name, form_desc_text in forms_info:
            form_card = QFrame()
            form_card.setObjectName("form-card")
            form_card.setMinimumHeight(50)
            
            card_layout = QHBoxLayout(form_card)
            card_layout.setContentsMargins(10, 5, 10, 5)
            
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            self.form_checkboxes[form_name] = checkbox
            
            form_info = QVBoxLayout()
            form_title = QLabel(form_name)
            form_title.setObjectName("form-title")
            form_subtitle = QLabel(form_desc_text)
            form_subtitle.setObjectName("form-subtitle")
            
            form_info.addWidget(form_title)
            form_info.addWidget(form_subtitle)
            
            card_layout.addWidget(checkbox)
            card_layout.addLayout(form_info)
            card_layout.addStretch()
            
            custom_layout.addWidget(form_card)
        
        form_layout.addWidget(self.custom_form_frame)
        
        # 连接信号
        self.form_selector.currentTextChanged.connect(self.on_form_selection_changed)
        
        left_layout.addWidget(form_group)
        
        # 同步类型选择 - 优化为卡片式
        type_group = QGroupBox("⚙️ 同步类型")
        type_layout = QVBoxLayout(type_group)
        
        self.sync_type_combo = QComboBox()
        self.sync_type_combo.addItems(["增量同步", "全量同步", "完全同步"])
        self.sync_type_combo.setMinimumHeight(40)
        type_layout.addWidget(self.sync_type_combo)
        
        # 添加说明文本
        type_desc = QLabel("增量: 只同步更新的数据\n全量: 同步所有数据\n完全: 清空后重新同步")
        type_desc.setObjectName("type-description")
        type_layout.addWidget(type_desc)
        
        left_layout.addWidget(type_group)
        
        # 操作按钮区域
        button_group = QGroupBox("🚀 操作控制")
        button_layout = QVBoxLayout(button_group)
        
        self.manual_sync_btn = QPushButton("🔄 开始手动同步")
        self.manual_sync_btn.setMinimumHeight(45)
        self.manual_sync_btn.setObjectName("primary-btn")
        self.manual_sync_btn.clicked.connect(self.start_manual_sync)
        
        button_row = QHBoxLayout()
        self.test_connection_btn = QPushButton("🔌 测试")
        self.test_connection_btn.setMinimumHeight(35)
        self.test_connection_btn.clicked.connect(self.test_connections)
        
        self.validate_data_btn = QPushButton("✓ 验证")
        self.validate_data_btn.setMinimumHeight(35)
        self.validate_data_btn.clicked.connect(self.validate_data)
        
        button_row.addWidget(self.test_connection_btn)
        button_row.addWidget(self.validate_data_btn)
        
        button_layout.addWidget(self.manual_sync_btn)
        button_layout.addLayout(button_row)
        
        left_layout.addWidget(button_group)
        left_layout.addStretch()
        
        layout.addWidget(left_panel)
        
        # 右侧状态区域
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 进度显示区域 - 优化设计
        progress_group = QGroupBox("📈 同步进度")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_label = QLabel("准备就绪")
        self.progress_label.setObjectName("progress-label")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(25)
        
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        
        right_layout.addWidget(progress_group)
        
        # 日志显示区域 - 增大高度
        log_group = QGroupBox("📜 实时日志")
        log_layout = QVBoxLayout(log_group)
        
        # 日志工具栏
        log_toolbar = QHBoxLayout()
        clear_log_btn = QPushButton("🗑️ 清空")
        clear_log_btn.setMaximumWidth(80)
        clear_log_btn.clicked.connect(self.clear_log)
        
        log_toolbar.addStretch()
        log_toolbar.addWidget(clear_log_btn)
        
        self.log_text = QTextEdit()
        self.log_text.setMinimumHeight(350)  # 增大日志区域高度
        self.log_text.setReadOnly(True)
        
        log_layout.addLayout(log_toolbar)
        log_layout.addWidget(self.log_text)
        
        right_layout.addWidget(log_group)
        
        layout.addWidget(right_panel)
        
        self.tab_widget.addTab(sync_widget, "🔄 数据同步")
    
    def create_schedule_tab(self):
        """创建定时同步标签页"""
        schedule_widget = QWidget()
        layout = QHBoxLayout(schedule_widget)
        layout.setSpacing(20)
        
        # 左侧设置区域
        left_panel = QWidget()
        left_panel.setFixedWidth(400)
        left_layout = QVBoxLayout(left_panel)
        
        # 定时设置区域
        timer_group = QGroupBox("⏰ 定时同步设置")
        timer_layout = QVBoxLayout(timer_group)
        
        # 自动同步开关
        auto_card = QFrame()
        auto_card.setObjectName("setting-card")
        auto_layout = QHBoxLayout(auto_card)
        auto_layout.setContentsMargins(15, 10, 15, 10)
        
        auto_info = QVBoxLayout()
        auto_title = QLabel("启用自动同步")
        auto_title.setObjectName("setting-title")
        auto_desc = QLabel("按设定间隔自动执行同步")
        auto_desc.setObjectName("setting-desc")
        
        auto_info.addWidget(auto_title)
        auto_info.addWidget(auto_desc)
        
        self.auto_sync_checkbox = QCheckBox()
        self.auto_sync_checkbox.setObjectName("toggle-switch")
        
        auto_layout.addLayout(auto_info)
        auto_layout.addStretch()
        auto_layout.addWidget(self.auto_sync_checkbox)
        
        timer_layout.addWidget(auto_card)
        
        # 同步间隔设置
        interval_card = QFrame()
        interval_card.setObjectName("setting-card")
        interval_layout = QVBoxLayout(interval_card)
        interval_layout.setContentsMargins(15, 10, 15, 10)
        
        interval_title = QLabel("同步间隔")
        interval_title.setObjectName("setting-title")
        
        interval_row = QHBoxLayout()
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(1, 1440)
        self.interval_spinbox.setValue(60)
        self.interval_spinbox.setSuffix(" 分钟")
        self.interval_spinbox.setMinimumHeight(35)
        
        interval_row.addWidget(QLabel("每"))
        interval_row.addWidget(self.interval_spinbox)
        interval_row.addWidget(QLabel("执行一次同步"))
        interval_row.addStretch()
        
        interval_layout.addWidget(interval_title)
        interval_layout.addLayout(interval_row)
        
        timer_layout.addWidget(interval_card)
        
        left_layout.addWidget(timer_group)
        
        # 控制按钮区域
        control_group = QGroupBox("🎮 调度控制")
        control_layout = QVBoxLayout(control_group)
        
        self.start_scheduler_btn = QPushButton("▶️ 启动调度")
        self.start_scheduler_btn.setMinimumHeight(45)
        self.start_scheduler_btn.setObjectName("primary-btn")
        self.start_scheduler_btn.clicked.connect(self.start_scheduler)
        
        control_row = QHBoxLayout()
        self.pause_scheduler_btn = QPushButton("⏸️ 暂停")
        self.pause_scheduler_btn.setMinimumHeight(35)
        self.pause_scheduler_btn.clicked.connect(self.pause_scheduler)
        self.pause_scheduler_btn.setEnabled(False)
        
        self.stop_scheduler_btn = QPushButton("⏹️ 停止")
        self.stop_scheduler_btn.setMinimumHeight(35)
        self.stop_scheduler_btn.clicked.connect(self.stop_scheduler)
        self.stop_scheduler_btn.setEnabled(False)
        
        control_row.addWidget(self.pause_scheduler_btn)
        control_row.addWidget(self.stop_scheduler_btn)
        
        control_layout.addWidget(self.start_scheduler_btn)
        control_layout.addLayout(control_row)
        
        left_layout.addWidget(control_group)
        left_layout.addStretch()
        
        layout.addWidget(left_panel)
        
        # 右侧状态区域
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 调度状态显示
        status_group = QGroupBox("📊 调度状态")
        status_layout = QVBoxLayout(status_group)
        
        # 状态卡片
        status_card = QFrame()
        status_card.setObjectName("status-display-card")
        status_card_layout = QVBoxLayout(status_card)
        status_card_layout.setContentsMargins(20, 15, 20, 15)
        
        self.scheduler_status_label = QLabel("状态: 已停止")
        self.scheduler_status_label.setObjectName("status-text")
        
        self.next_sync_label = QLabel("下次同步: 无")
        self.next_sync_label.setObjectName("next-sync-text")
        
        status_card_layout.addWidget(self.scheduler_status_label)
        status_card_layout.addWidget(self.next_sync_label)
        
        status_layout.addWidget(status_card)
        
        right_layout.addWidget(status_group)
        
        # 最近同步记录
        recent_group = QGroupBox("📅 最近同步记录")
        recent_layout = QVBoxLayout(recent_group)
        
        self.recent_sync_text = QTextEdit()
        self.recent_sync_text.setMinimumHeight(300)
        self.recent_sync_text.setReadOnly(True)
        recent_layout.addWidget(self.recent_sync_text)
        
        right_layout.addWidget(recent_group)
        
        layout.addWidget(right_panel)
        
        self.tab_widget.addTab(schedule_widget, "⏰ 定时同步")
    
    def create_history_tab(self):
        """创建历史记录标签页"""
        history_widget = QWidget()
        layout = QVBoxLayout(history_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 顶部工具栏
        toolbar = QHBoxLayout()
        
        # 统计信息
        stats_frame = QFrame()
        stats_frame.setObjectName("stats-frame")
        stats_layout = QHBoxLayout(stats_frame)
        
        self.total_syncs_label = QLabel("总同步次数: 0")
        self.success_rate_label = QLabel("成功率: 0%")
        self.last_success_label = QLabel("最后成功: 无")
        
        stats_layout.addWidget(self.total_syncs_label)
        stats_layout.addWidget(QLabel(" | "))
        stats_layout.addWidget(self.success_rate_label)
        stats_layout.addWidget(QLabel(" | "))
        stats_layout.addWidget(self.last_success_label)
        stats_layout.addStretch()
        
        # 操作按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setObjectName("action-btn")
        refresh_btn.clicked.connect(self.refresh_history)
        
        export_btn = QPushButton("💾 导出")
        export_btn.setObjectName("action-btn")
        export_btn.clicked.connect(self.export_history)
        
        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.setObjectName("danger-btn")
        clear_btn.clicked.connect(self.clear_history)
        
        toolbar.addWidget(stats_frame)
        toolbar.addStretch()
        toolbar.addWidget(refresh_btn)
        toolbar.addWidget(export_btn)
        toolbar.addWidget(clear_btn)
        
        layout.addLayout(toolbar)
        
        # 过滤区域
        filter_frame = QFrame()
        filter_frame.setObjectName("filter-frame")
        filter_layout = QHBoxLayout(filter_frame)
        
        filter_layout.addWidget(QLabel("过滤:"))
        
        self.date_filter = QComboBox()
        self.date_filter.addItems(["所有时间", "今天", "最近三天", "最近一周", "最近一月"])
        
        self.status_filter = QComboBox()
        self.status_filter.addItems(["所有状态", "成功", "失败", "部分成功"])
        
        self.type_filter = QComboBox()
        self.type_filter.addItems(["所有类型", "增量同步", "全量同步", "完全同步"])
        
        filter_layout.addWidget(self.date_filter)
        filter_layout.addWidget(self.status_filter)
        filter_layout.addWidget(self.type_filter)
        filter_layout.addStretch()
        
        layout.addWidget(filter_frame)
        
        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(9)
        self.history_table.setHorizontalHeaderLabels([
            "状态", "同步类型", "表名", "操作", "记录数", "消息", "开始时间", "结束时间", "耗时(秒)"
        ])
        
        # 设置表格属性
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setSortingEnabled(True)
        
        # 设置列宽
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 状态
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 类型
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 表名
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 操作
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 记录数
        header.setSectionResizeMode(5, QHeaderView.Stretch)           # 消息
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 开始时间
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # 结束时间
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # 耗时
        
        layout.addWidget(self.history_table)
        
        self.tab_widget.addTab(history_widget, "📊 历史记录")
    
    def create_settings_tab(self):
        """创建设置标签页"""
        settings_widget = QScrollArea()
        settings_content = QWidget()
        layout = QVBoxLayout(settings_content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 金蝶API设置
        kingdee_group = QGroupBox("🌐 金蝶API设置")
        kingdee_layout = QVBoxLayout(kingdee_group)
        
        # API连接信息卡片
        api_card = QFrame()
        api_card.setObjectName("config-card")
        api_layout = QVBoxLayout(api_card)
        api_layout.setContentsMargins(20, 15, 20, 15)
        
        api_title = QLabel("当前API配置")
        api_title.setObjectName("config-title")
        
        kingdee_info = QLabel("""• 登录地址: https://jyxing.ik3cloud.com/k3cloud/...
• 账套ID: 20211115163118805
• 用户名: aps
• 语言代码: 2052

🔧 如需修改配置，请编辑 config.ini 文件""")
        kingdee_info.setObjectName("config-info")
        
        api_layout.addWidget(api_title)
        api_layout.addWidget(kingdee_info)
        
        kingdee_layout.addWidget(api_card)
        layout.addWidget(kingdee_group)
        
        # MySQL数据库设置
        mysql_group = QGroupBox("💾 MySQL数据库设置")
        mysql_layout = QVBoxLayout(mysql_group)
        
        # 数据库连接信息卡片
        db_card = QFrame()
        db_card.setObjectName("config-card")
        db_layout = QVBoxLayout(db_card)
        db_layout.setContentsMargins(20, 15, 20, 15)
        
        db_title = QLabel("当前数据库配置")
        db_title.setObjectName("config-title")
        
        mysql_info = QLabel("""• 主机地址: 192.169.0.32
• 数据库名: kingdee
• 用户名: root
• 端口: 3306
• 字符集: utf8mb4

🔧 如需修改配置，请编辑 config.ini 文件""")
        mysql_info.setObjectName("config-info")
        
        db_layout.addWidget(db_title)
        db_layout.addWidget(mysql_info)
        
        mysql_layout.addWidget(db_card)
        layout.addWidget(mysql_group)
        
        # 数据表结构信息
        tables_group = QGroupBox("📋 数据表结构")
        tables_layout = QVBoxLayout(tables_group)
        
        tables_card = QFrame()
        tables_card.setObjectName("config-card")
        tables_card_layout = QVBoxLayout(tables_card)
        tables_card_layout.setContentsMargins(20, 15, 20, 15)
        
        tables_title = QLabel("自动创建的数据表")
        tables_title.setObjectName("config-title")
        
        tables_info = QLabel("""• sales_orders - 销售订单数据表
• sales_outstock - 销售出库单数据表
• forecast_orders - 预测订单数据表
• prd_ppbom - 生产用料清单数据表
• sync_logs - 同步操作日志表

📊 所有数据表将在首次运行时自动创建""")
        tables_info.setObjectName("config-info")
        
        tables_card_layout.addWidget(tables_title)
        tables_card_layout.addWidget(tables_info)
        
        tables_layout.addWidget(tables_card)
        layout.addWidget(tables_group)
        
        # 系统信息
        about_group = QGroupBox("ℹ️ 关于系统")
        about_layout = QVBoxLayout(about_group)
        
        about_card = QFrame()
        about_card.setObjectName("config-card")
        about_card_layout = QVBoxLayout(about_card)
        about_card_layout.setContentsMargins(20, 15, 20, 15)
        
        app_title = QLabel("🚀 金蝶数据同步工具 v1.0")
        app_title.setObjectName("app-title")
        
        about_info = QLabel("""🎆 功能特性:
• 支持销售订单、销售出库单、预测订单、生产订单、生产用料清单数据同步
• 提供增量、全量、完全同步三种模式
• 支持自动定时同步和手动同步
• 实时进度显示和日志记录
• Windows 11风格现代化界面

🛠️ 技术架构:
• 前端: PySide6 (Qt6)
• 后端: Python 3.11+
• 数据库: MySQL
• 网络通信: requests""")
        about_info.setObjectName("config-info")
        
        about_card_layout.addWidget(app_title)
        about_card_layout.addWidget(about_info)
        
        about_layout.addWidget(about_card)
        layout.addWidget(about_group)
        
        layout.addStretch()
        
        settings_widget.setWidget(settings_content)
        self.tab_widget.addTab(settings_widget, "⚙️ 设置")
    
    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.connection_status_label = QLabel("连接状态: 未知")
        self.last_sync_label = QLabel("最后同步: 无")
        
        self.status_bar.addWidget(self.connection_status_label)
        self.status_bar.addPermanentWidget(self.last_sync_label)
    
    def quick_sync(self):
        """快速同步"""
        # 设置为同步所有表单进行增量同步
        self.form_selector.setCurrentText("同步所有表单")
        self.sync_type_combo.setCurrentText("增量同步")
        self.start_manual_sync()
    
    def clear_log(self):
        """清空日志"""
        self.log_text.clear()
        self.log_message("日志已清空")
    
    def export_history(self):
        """导出历史记录"""
        # TODO: 实现导出功能
        QMessageBox.information(self, "提示", "导出功能将在后续版本中实现")
    
    def clear_history(self):
        """清空历史记录"""
        reply = QMessageBox.question(self, "确认操作", "确定要清空所有历史记录吗？", 
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            # TODO: 实现清空功能
            QMessageBox.information(self, "提示", "清空功能将在后续版本中实现")
    
    def on_form_selection_changed(self, selection_text: str):
        """表单选择变化处理"""
        if selection_text == "自定义选择...":
            # 显示自定义选择框
            self.custom_form_frame.setVisible(True)
            self.log_message("已切换到自定义选择模式")
        else:
            # 隐藏自定义选择框
            self.custom_form_frame.setVisible(False)
            if selection_text == "同步所有表单":
                self.log_message("已选择同步所有表单")
            else:
                self.log_message(f"已选择同步: {selection_text}")
    
    def setup_connections(self):
        """设置信号连接"""
        self.auto_sync_checkbox.toggled.connect(self.toggle_auto_sync)
        self.interval_spinbox.valueChanged.connect(self.update_sync_interval)
        self.sync_type_combo.currentTextChanged.connect(self.update_sync_type)
        
        auto_scheduler.add_status_callback(self.on_scheduler_status_changed)
        auto_scheduler.add_sync_callback(self.on_sync_completed)
    
    def setup_timer(self):
        """设置定时器"""
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)
    
    def apply_theme(self):
        """应用Windows 11渐变淡紫色主题"""
        try:
            # 获取项目根目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            css_file_path = os.path.join(project_root, 'assets', 'styles.css')
            
            # 读取CSS文件
            with open(css_file_path, 'r', encoding='utf-8') as f:
                style = f.read()
            
            # 应用样式
            self.setStyleSheet(style)
            
        except FileNotFoundError:
            # 如果CSS文件不存在，使用默认样式
            print("警告: styles.css文件未找到，使用默认样式")
            self.setStyleSheet("")
        except Exception as e:
            # 如果读取CSS文件出错，使用默认样式
            print(f"警告: 读取CSS文件时出错: {e}，使用默认样式")
            self.setStyleSheet("")
    
    def start_manual_sync(self):
        """启动手动同步"""
        selected_forms = self.get_selected_forms()
        if not selected_forms:
            QMessageBox.warning(self, "警告", "请至少选择一个表单进行同步！")
            return
        
        sync_type = self.get_current_sync_type()
        
        self.manual_sync_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.sync_worker = SyncWorker(selected_forms, sync_type)
        self.sync_worker.progress.connect(self.update_progress)
        self.sync_worker.finished.connect(self.on_manual_sync_finished)
        self.sync_worker.start()
        
        self.log_message(f"开始手动同步: {', '.join(selected_forms)} ({sync_type.value})")
    
    def test_connections(self):
        """测试连接"""
        from src.core.kingdee_api import kingdee_client
        from src.core.mysql_manager import mysql_manager
        
        self.log_message("正在测试连接...")
        
        kingdee_ok = kingdee_client.test_connection()
        mysql_ok = mysql_manager.test_connection()
        
        if kingdee_ok and mysql_ok:
            status_msg = "连接状态: 正常"
            self.log_message("✓ 所有连接测试通过")
            QMessageBox.information(self, "连接测试", "金蝶API和MySQL数据库连接正常！")
        else:
            status_msg = "连接状态: 异常"
            errors = []
            if not kingdee_ok:
                errors.append("金蝶API连接失败")
            if not mysql_ok:
                errors.append("MySQL数据库连接失败")
            
            error_msg = "、".join(errors)
            self.log_message(f"✗ 连接测试失败: {error_msg}")
            QMessageBox.critical(self, "连接测试失败", f"连接测试失败:\n{error_msg}")
        
        self.connection_status_label.setText(status_msg)
    
    def validate_data(self):
        """验证数据完整性"""
        selected_forms = self.get_selected_forms()
        if not selected_forms:
            QMessageBox.warning(self, "警告", "请至少选择一个表单进行验证！")
            return
        
        self.log_message("开始数据完整性验证...")
        
        try:
            results = sync_manager.validate_data_integrity(selected_forms)
            
            validation_text = "数据完整性验证结果:\n\n"
            all_match = True
            
            for form_name, result in results.items():
                if 'error' in result:
                    validation_text += f"{form_name}: 验证失败 - {result['error']}\n"
                    all_match = False
                else:
                    kingdee_count = result['kingdee_count']
                    db_count = result['database_count']
                    match = result['match']
                    
                    status = "✓ 一致" if match else "✗ 不一致"
                    validation_text += f"{form_name}: {status}\n"
                    validation_text += f"  金蝶记录数: {kingdee_count}\n"
                    validation_text += f"  数据库记录数: {db_count}\n"
                    
                    if not match:
                        validation_text += f"  差异: {result['difference']} 条\n"
                        all_match = False
                    
                    validation_text += "\n"
            
            if all_match:
                QMessageBox.information(self, "验证结果", validation_text)
            else:
                QMessageBox.warning(self, "验证结果", validation_text)
            
            self.log_message("数据完整性验证完成")
            
        except Exception as e:
            error_msg = f"数据验证失败: {str(e)}"
            self.log_message(error_msg)
            QMessageBox.critical(self, "验证失败", error_msg)
    
    def get_selected_forms(self) -> List[str]:
        """获取选中的表单"""
        selection = self.form_selector.currentText()
        
        if selection == "同步所有表单":
            # 返回所有表单
            return ["销售订单", "销售出库单", "预测订单", "生产订单", "生产用料清单"]
        elif selection == "自定义选择...":
            # 使用复选框的选择结果
            selected = []
            for form_name, checkbox in self.form_checkboxes.items():
                if checkbox.isChecked():
                    selected.append(form_name)
            return selected
        elif selection in ["销售订单", "销售出库单", "预测订单", "生产订单", "生产用料清单"]:
            # 返回单个选择的表单
            return [selection]
        else:
            # 默认返回所有表单
            return ["销售订单", "销售出库单", "预测订单", "生产订单", "生产用料清单"]
    
    def get_current_sync_type(self) -> SyncType:
        """获取当前同步类型"""
        type_text = self.sync_type_combo.currentText()
        if type_text == "增量同步":
            return SyncType.INCREMENTAL
        elif type_text == "全量同步":
            return SyncType.FULL
        else:
            return SyncType.COMPLETE
    
    def update_progress(self, message: str, progress: int):
        """更新进度"""
        self.progress_label.setText(message)
        self.progress_bar.setValue(progress)
        self.log_message(message)
    
    def on_manual_sync_finished(self, result: dict):
        """手动同步完成"""
        self.manual_sync_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if result['status'] == 'success':
            self.log_message(f"✓ 手动同步成功: {result['message']}")
            # QMessageBox.information(self, "同步完成", f"同步成功!\n{result['message']}")  # 取消同步成功弹窗
        else:
            self.log_message(f"✗ 手动同步失败: {result['message']}")
            QMessageBox.critical(self, "同步失败", f"同步失败!\n{result['message']}")
        
        self.update_last_sync_time()
        self.refresh_history()
    
    def toggle_auto_sync(self, enabled: bool):
        """切换自动同步"""
        if enabled:
            self.start_scheduler()
        else:
            self.stop_scheduler()
    
    def update_sync_interval(self, interval: int):
        """更新同步间隔"""
        if auto_scheduler.status == SchedulerStatus.RUNNING:
            auto_scheduler.update_interval(interval)
    
    def update_sync_type(self, type_text: str):
        """更新同步类型"""
        sync_type = self.get_current_sync_type()
        auto_scheduler.update_sync_type(sync_type)
    
    def start_scheduler(self):
        """启动调度器"""
        selected_forms = self.get_selected_forms()
        if not selected_forms:
            QMessageBox.warning(self, "警告", "请至少选择一个表单进行自动同步！")
            self.auto_sync_checkbox.setChecked(False)
            return
        
        sync_type = self.get_current_sync_type()
        interval = self.interval_spinbox.value()
        
        auto_scheduler.configure_sync(selected_forms, sync_type, interval)
        auto_scheduler.start()
        
        self.log_message(f"启动自动同步调度器: 间隔 {interval} 分钟")
    
    def pause_scheduler(self):
        """暂停调度器"""
        auto_scheduler.pause()
        self.log_message("暂停自动同步调度器")
    
    def stop_scheduler(self):
        """停止调度器"""
        auto_scheduler.stop()
        self.auto_sync_checkbox.setChecked(False)
        self.log_message("停止自动同步调度器")
    
    def on_scheduler_status_changed(self, status: SchedulerStatus, message: str):
        """调度器状态变化"""
        status_text = {
            SchedulerStatus.STOPPED: "已停止",
            SchedulerStatus.RUNNING: "运行中",
            SchedulerStatus.PAUSED: "已暂停"
        }
        
        self.scheduler_status_label.setText(f"状态: {status_text[status]}")
        
        # 更新按钮状态
        if status == SchedulerStatus.RUNNING:
            self.start_scheduler_btn.setEnabled(False)
            self.pause_scheduler_btn.setEnabled(True)
            self.stop_scheduler_btn.setEnabled(True)
        elif status == SchedulerStatus.PAUSED:
            self.start_scheduler_btn.setEnabled(True)
            self.pause_scheduler_btn.setEnabled(False)
            self.stop_scheduler_btn.setEnabled(True)
        else:
            self.start_scheduler_btn.setEnabled(True)
            self.pause_scheduler_btn.setEnabled(False)
            self.stop_scheduler_btn.setEnabled(False)
    
    def on_sync_completed(self, result: dict):
        """同步完成回调"""
        self.log_message(f"自动同步完成: {result['message']}")
        self.update_last_sync_time()
        self.refresh_history()
    
    def update_status(self):
        """更新状态"""
        # 更新下次同步时间
        next_sync = auto_scheduler.get_next_sync_time()
        if next_sync:
            self.next_sync_label.setText(f"下次同步: {next_sync.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            self.next_sync_label.setText("下次同步: 无")
    
    def update_last_sync_time(self):
        """更新最后同步时间"""
        sync_config = config_manager.get_sync_config()
        last_sync = sync_config.get('last_sync_time', '')
        if last_sync:
            self.last_sync_label.setText(f"最后同步: {last_sync}")
        else:
            self.last_sync_label.setText("最后同步: 无")
    
    def refresh_history(self):
        """刷新历史记录"""
        try:
            history = sync_manager.get_sync_history(50)
            
            self.history_table.setRowCount(len(history))
            
            for row, record in enumerate(history):
                self.history_table.setItem(row, 0, QTableWidgetItem(record.get('sync_type', '')))
                self.history_table.setItem(row, 1, QTableWidgetItem(record.get('table_name', '')))
                self.history_table.setItem(row, 2, QTableWidgetItem(record.get('operation', '')))
                self.history_table.setItem(row, 3, QTableWidgetItem(str(record.get('record_count', 0))))
                self.history_table.setItem(row, 4, QTableWidgetItem(record.get('status', '')))
                self.history_table.setItem(row, 5, QTableWidgetItem(record.get('message', '')))
                self.history_table.setItem(row, 6, QTableWidgetItem(str(record.get('start_time', ''))))
                self.history_table.setItem(row, 7, QTableWidgetItem(str(record.get('duration_seconds', 0))))
            
        except Exception as e:
            self.log_message(f"刷新历史记录失败: {str(e)}")
    
    def log_message(self, message: str):
        """记录日志消息"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        self.log_text.append(log_entry)
        
        # 自动滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
    
    def load_initial_status(self):
        """加载初始状态"""
        self.update_last_sync_time()
        self.refresh_history()
        
        # 恢复同步设置
        sync_config = config_manager.get_sync_config()
        self.interval_spinbox.setValue(sync_config.get('sync_interval', 60))
        
        sync_type = sync_config.get('sync_type', 'incremental')
        if sync_type == 'incremental':
            self.sync_type_combo.setCurrentText('增量同步')
        elif sync_type == 'full':
            self.sync_type_combo.setCurrentText('全量同步')
        else:
            self.sync_type_combo.setCurrentText('完全同步')
        
        # 如果配置了自动同步，恢复状态
        if sync_config.get('auto_sync', False):
            self.auto_sync_checkbox.setChecked(True)
        
        self.log_message("金蝶数据同步工具已启动")
    
    def closeEvent(self, event):
        """关闭事件"""
        # 停止调度器
        if auto_scheduler.status != SchedulerStatus.STOPPED:
            auto_scheduler.stop()
        
        # 关闭数据库连接
        from src.core.mysql_manager import mysql_manager
        mysql_manager.disconnect()
        
        event.accept()