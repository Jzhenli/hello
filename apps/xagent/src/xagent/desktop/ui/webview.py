"""WebView management component."""

import logging
import toga
from toga.style import Pack
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class WebViewManager:
    """Manages the WebView component with cross-platform support."""

    def __init__(self):
        self.webview = None
        self._has_reloaded = False  # Prevent infinite reload loops

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
        self._has_reloaded = False  # Reset reload flag
        self.webview = toga.WebView(
            url=url,
            style=Pack(flex=1),
            on_webview_load=on_webview_load
        )
        return self.webview
    
    async def clear_cache_and_reload(self) -> bool:
        """Force reload the page to ensure fresh content.
        
        This method forces a page reload to prevent caching issues.
        It does NOT clear localStorage/sessionStorage to preserve user sessions.
        
        The HTML meta tags and Vite's content-hash filenames provide sufficient
        cache busting for static assets.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.webview:
            return False
        
        # Prevent infinite reload loops
        if self._has_reloaded:
            logger.info("Reload already performed, skipping to prevent infinite loop")
            return True
        
        self._has_reloaded = True
        logger.info("Forcing page reload")
        
        try:
            # Force reload without clearing user data
            # The HTML meta tags handle cache control for HTML
            # Vite's content-hash filenames handle cache busting for JS/CSS
            js_code = """
            (function() {
                try {
                    // Force reload from server
                    // This ensures we get the latest HTML with correct JS/CSS filenames
                    location.reload(true);
                    return 'Page reloading';
                } catch(e) {
                    console.error('Error during reload:', e);
                    return 'Error: ' + e.message;
                }
            })();
            """
            
            result = await self.webview.evaluate_javascript(js_code)
            
            # Check if JavaScript evaluation failed
            # On Android/Windows: None result indicates an error (no exception thrown)
            # On Linux/macOS/iOS: exceptions are thrown on error, so None won't occur
            # But checking for None is safe for all platforms
            if result is None:
                raise RuntimeError("JavaScript evaluation returned None (likely an error)")
            
            logger.info(f"Reload result: {result}")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to reload via JavaScript: {e}")
            return self._fallback_reload()
    
    def _fallback_reload(self) -> bool:
        """Fallback method to reload the page by resetting URL.
        
        Returns:
            bool: True if fallback was attempted
        """
        current_url = self.webview.url if self.webview else None
        if current_url:
            logger.info("Falling back to URL reload")
            self.webview.url = current_url
            return True
        return False
