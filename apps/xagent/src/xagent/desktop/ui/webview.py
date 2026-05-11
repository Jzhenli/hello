"""WebView management component."""

import logging
import toga
from toga.style import Pack
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class WebViewManager:
    """Manages the WebView component."""

    def __init__(self):
        self.webview = None

    def create_webview(
        self,
        url: str,
        on_webview_load: Optional[Callable] = None
    ) -> toga.WebView:
        """Create a WebView with the specified URL.
        
        Args:
            url: The URL to load
            on_webview_load: Optional callback for when the page loads
        """
        logger.info(f"Loading WebView: {url}")
        self.webview = toga.WebView(
            url=url,
            style=Pack(flex=1),
            on_webview_load=on_webview_load
        )
        return self.webview

    def load_url(self, url: str) -> None:
        """Load a new URL in the WebView."""
        if self.webview:
            logger.info(f"Loading new URL in WebView: {url}")
            self.webview.url = url
