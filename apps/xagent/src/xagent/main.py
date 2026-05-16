"""XAgent Entry Point - Supports both CLI and Desktop modes"""

import argparse
import logging
import platform
from pathlib import Path

logger = logging.getLogger(__name__)


def setup_logging(debug: bool = False):
    """配置日志"""
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


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
    
    force_cli = args.cli
    force_desktop = args.desktop
    
    if force_cli:
        from .xcore.run import main as cli_main
        cli_main()
    elif force_desktop:
        from .desktop import main as desktop_main
        desktop_main()
    # elif platform.system() == "Windows":
    #     from .xcore.run import main as cli_main
    #     cli_main()
    else:
        from .desktop import main as desktop_main
        desktop_main()


if __name__ == "__main__":
    main()
