"""WebView management component."""

import logging
import toga
from toga.style import Pack
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class WebViewManager:
    """Manages the WebView component with cross-platform support."""

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
        
        Note:
            No force reload is needed because the backend serves HTML with
            no-cache headers and JS/CSS use content-hash filenames (Vite).
            This ensures webview always gets the latest content without
            the visual disruption of a page reload.
        """
        logger.info(f"Loading WebView: {url}")
        self.webview = toga.WebView(
            url=url,
            style=Pack(flex=1),
            on_webview_load=on_webview_load
        )
        return self.webview
