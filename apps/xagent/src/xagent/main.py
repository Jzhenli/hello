"""XAgent Entry Point - Supports both CLI and Desktop modes"""

import argparse
import logging
import platform
from pathlib import Path

logger = logging.getLogger(__name__)


def setup_logging(debug: bool = False):
    """配置日志"""
    from .xcore.core.logging import _ensure_utf8_encoding
    
    _ensure_utf8_encoding()
    
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def patch_windows_selector():
    """修复 Windows 上 SelectorEventLoop 的 WinError 10038 问题
    
    问题描述：
    Windows 的 select() 只支持 socket，不支持管道等其他文件描述符。
    当事件循环关闭时，如果 selector 中有非 socket 资源，会触发 WinError 10038。
    
    解决方案：
    参考 https://bugs.python.org/issue33350
    在 SelectSelector._select 中捕获该错误并返回空列表。
    """
    from selectors import SelectSelector
    
    # 保存原始方法
    _original_select = SelectSelector._select
    
    def _patched_select(self, r, w, x, timeout=None):
        try:
            return _original_select(self, r, w, x, timeout)
        except OSError as e:
            if hasattr(e, 'winerror') and e.winerror == 10038:
                # 文件描述符可能已经关闭，返回空列表
                return [], [], []
            raise
    
    SelectSelector._select = _patched_select
    logger.debug("Windows SelectorEventLoop patch applied (WinError 10038 fix)")


def main():
    """Main entry point - routes to appropriate mode."""
    parser = argparse.ArgumentParser(description="XAgent IoT Gateway")
    parser.add_argument(
        '--cli', '-c',
        action='store_true',
        help='Force CLI mode'
    )
    parser.add_argument(
        '--desktop', '-d',
        action='store_true',
        help='Force desktop mode'
    )
    parser.add_argument(
        '--config',
        type=str,
        help='Config file path'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        help='Data directory path (overrides default path)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )
    parser.add_argument(
        '--init-config',
        action='store_true',
        help='Create default config file and exit'
    )
    
    args = parser.parse_args()
    
    setup_logging(args.debug)
    
    from .xcore.core.paths import AppPaths
    custom_base_dir = Path(args.data_dir) if args.data_dir else None
    paths = AppPaths.initialize(custom_base_dir)
    
    if args.init_config:
        config_file = paths.config_file
        if not config_file.exists():
            from .xcore.core.config import ConfigManager
            ConfigManager(config_path=str(config_file), paths=paths)
            logger.info(f"Default config file created: {config_file}")
        else:
            logger.info(f"Config file already exists: {config_file}")
        return
    
    if args.debug:
        logger.info("Application path info:")
        for key, value in paths.get_all_paths_info().items():
            logger.info(f"  {key}: {value}")
    
    # 确定运行模式
    force_cli = args.cli
    force_desktop = args.desktop
    
    if force_cli:
        use_cli_mode = True
    elif force_desktop:
        use_cli_mode = False
    else:
        # 根据平台自动选择模式
        from .xcore.utils.platform_utils import get_os_platform
        os_platform = get_os_platform()
        
        # Android 使用 desktop 模式（toga 移动端）
        # 其他平台使用 CLI 模式（支持 aiomqtt）
        use_cli_mode = (os_platform != "Android")
        
        if args.debug:
            logger.info(f"Auto-detected platform: {os_platform}, using {'CLI' if use_cli_mode else 'Desktop'} mode")
    
    # CLI 模式需要设置 SelectorEventLoop 以支持 aiomqtt
    if use_cli_mode and platform.system() == "Windows":
        from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy
        set_event_loop_policy(WindowsSelectorEventLoopPolicy())
        # 修复 Windows SelectorEventLoop 的 WinError 10038 问题
        patch_windows_selector()
    
    if use_cli_mode:
        from .xcore.run import main as cli_main
        cli_main()
    else:
        from .desktop import main as desktop_main
        desktop_main()


if __name__ == "__main__":
    main()
