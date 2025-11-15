"""日志配置模块

使用 loguru 提供统一的日志记录功能。
"""

import sys

from loguru import logger

# 移除默认的 handler
logger.remove()

# 添加自定义 handler
# 格式：时间 | 级别 | 文件:行号 | 消息
logger.add(
    sys.stderr,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    ),
    level="INFO",
    colorize=True,
)

# 导出 logger 供其他模块使用
__all__ = ["logger"]
