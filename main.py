#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
金蝶云星空数据同步工具 - 主入口文件

这是重构后的项目主入口文件，用于启动GUI应用程序。
项目已按功能模块重新组织文件结构：

- src/: 源代码目录
  - core/: 核心业务逻辑（API、数据同步、数据库管理、调度器）
  - gui/: GUI界面相关文件
  - config/: 配置管理
  - utils/: 工具脚本
- assets/: 静态资源（CSS样式文件）
- data/: 数据文件
- scripts/: 构建和启动脚本
- docs/: 文档文件

作者: AI Assistant
创建时间: 2024年
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 导入主程序
from src.utils.kingdee_sync_tool import main

if __name__ == "__main__":
    # 启动主程序
    main()