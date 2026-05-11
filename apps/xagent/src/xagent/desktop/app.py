"""Toga Desktop Application Main Class."""

import asyncio
import logging
from typing import Optional

import toga

from .config import DesktopConfig
from .platform import setup_platform
from .startup import BackendManager
from .ui import SplashScreen, ErrorScreen, WebViewManager

setup_platform()

logger = logging.getLogger(__name__)


class XAgentDesktopApp(toga.App):
    """Main desktop application class."""

    def __init__(self, config: Optional[DesktopConfig] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config or DesktopConfig.default()
        self._setup_components()

    def _setup_components(self):
        """Initialize UI and backend components."""
        self.backend_manager = BackendManager(self.config)
        self.splash_screen = SplashScreen(self.config.splash)
        self.webview_manager = WebViewManager()
        self.error_screen = ErrorScreen(self.config.error_screen)

    def startup(self) -> None:
        """Start the application - UI first, then backend."""
        self.main_window = toga.Window(
            title=self.config.window.title,
            size=(self.config.window.width, self.config.window.height),
        )

        splash_ui = self.splash_screen.create_ui()
        self.main_window.content = splash_ui
        self.main_window.show()

        self.on_exit = self.cleanup

        asyncio.create_task(self._delayed_start())

    async def _delayed_start(self):
        """Delay start to let UI render first."""
        await asyncio.sleep(0.15)
        await self._start_backend()

    async def _start_backend(self):
        """Start the backend services."""
        success, error = await self.backend_manager.start(
            self.splash_screen.update_progress
        )

        if not success:
            self._show_error(error)
            return

        asyncio.create_task(self.backend_manager.wait_for_socket())
        await self._show_main_ui()

    async def _show_main_ui(self):
        """Show the main UI with WebView."""
        self.splash_screen.update_progress(5)
        
        host = self.backend_manager.server_host
        if host == "0.0.0.0":
            host = "127.0.0.1"
        
        url = f"http://{host}:{self.backend_manager.server_port}/"
        webview = self.webview_manager.create_webview(url=url)
        self.main_window.content = webview

    def _show_error(self, message: str):
        """Show an error message."""
        error_ui = self.error_screen.create_ui(message)
        self.main_window.content = error_ui
        self.main_window.show()

    async def cleanup(self, app, **kwargs):
        """Cleanup resources on exit."""
        logger.info("Exiting XAgent Desktop App...")

        try:
            await self.backend_manager.stop()
        except Exception as e:
            logger.error(f"Error stopping backend: {e}")

        return True


def main() -> None:
    """Main entry point for the desktop application."""
    config = DesktopConfig.default()
    app = XAgentDesktopApp(
        config=config,
        formal_name=config.formal_name,
        app_id=config.app_id,
        app_name=config.app_name,
    )
    app.main_loop()


if __name__ == "__main__":
    main()
