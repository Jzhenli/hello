"""Run script for XAgent Gateway with API server"""

import asyncio
import logging
import os
import sys
import threading

from .core import ConfigManager, setup_logging
from .gateway import Gateway
from .api import app
from .api.dependencies import set_gateway_storage
import uvicorn

logger = logging.getLogger(__name__)


async def run_plugins(gateway: Gateway, shutdown_event: asyncio.Event):
    try:
        plugins_task = asyncio.create_task(gateway.start_plugins())

        await shutdown_event.wait()

        if not plugins_task.done():
            plugins_task.cancel()
            try:
                await plugins_task
            except asyncio.CancelledError:
                pass
    except asyncio.CancelledError:
        pass


async def async_main():
    config_manager = ConfigManager()
    config = config_manager.load()

    setup_logging(config.logging)

    logger.info("Starting XAgent Gateway...")

    gateway = Gateway(config_manager=config_manager)
    await gateway.initialize()
    await gateway.start_core()

    # Gateway.initialize() 已经设置了依赖注入，无需重复调用

    shutdown_event = asyncio.Event()

    # 创建 uvicorn server
    uvicorn_config = uvicorn.Config(
        app=app,
        host=config.server.host,
        port=config.server.port,
        reload=False,
        log_level=config.logging.level.lower(),
        access_log=False,
        log_config=None
    )
    server = uvicorn.Server(uvicorn_config)

    plugins_task = asyncio.create_task(run_plugins(gateway, shutdown_event))

    try:
        await server.serve()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        shutdown_event.set()
    finally:
        plugins_task.cancel()
        try:
            await plugins_task
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

        try:
            await gateway.stop()
        except Exception as e:
            logger.error(f"Error during gateway shutdown: {e}")


def main():
    """主入口函数
    
    退出策略：
    1. 正常情况：使用 sys.exit(0) 优雅退出
    2. 有非 daemon 线程阻塞：使用 os._exit(0) 强制退出
    """
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        logger.info("Event loop closed")

    # 检查是否有非 daemon 线程阻止退出
    non_daemon_threads = [
        t for t in threading.enumerate() 
        if t.is_alive() and t != threading.current_thread() and not t.daemon
    ]
    
    if non_daemon_threads:
        # 有非 daemon 线程，需要强制退出
        logger.warning(
            f"Non-daemon threads preventing clean exit: {[t.name for t in non_daemon_threads]}. "
            f"Using os._exit() for immediate termination."
        )
        os._exit(0)
    else:
        # 正常退出
        sys.exit(0)


if __name__ == "__main__":
    main()
