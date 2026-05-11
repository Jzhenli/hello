"""Run script for XAgent Gateway with API server"""

import asyncio
import logging
import platform
import signal

if platform.system() == "Windows":
    from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy
    set_event_loop_policy(WindowsSelectorEventLoopPolicy())

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

    from .storage import SQLiteStorage, WriteBehindBuffer
    from .core.metadata import MetadataManager
    from .api.services.command_executor import CommandExecutor

    set_gateway_storage(
        storage=gateway.container.resolve(SQLiteStorage),
        buffer=gateway.container.resolve(WriteBehindBuffer),
        metadata_manager=gateway.container.resolve(MetadataManager),
        command_executor=gateway.container.resolve(CommandExecutor),
        gateway=gateway,
        cleanup_task=gateway.cleanup_task
    )

    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("Received shutdown signal")
        shutdown_event.set()

    if platform.system() != "Windows":
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_event_loop().add_signal_handler(sig, signal_handler)

    plugins_task = asyncio.create_task(run_plugins(gateway, shutdown_event))

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
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(async_main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
