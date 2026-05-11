"""Error screen UI component."""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN
from typing import Optional

from ..config import ErrorScreenConfig


class ErrorScreen:
    """Error screen UI component."""

    def __init__(self, config: Optional[ErrorScreenConfig] = None):
        self.config = config or ErrorScreenConfig()

    def create_ui(self, message: str) -> toga.Box:
        """
        Create the error screen UI.
        
        Args:
            message: Error message to display
            
        Returns:
            Toga Box containing the error UI
        """
        error_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                align_items='center',
                margin=40,
                flex=1,
            )
        )

        error_title = toga.Label(
            self.config.title,
            style=Pack(
                font_size=self.config.title_font_size,
                font_weight='bold',
                margin_bottom=16,
                color=self.config.title_color,
            )
        )
        error_box.add(error_title)

        error_label = toga.Label(
            message,
            style=Pack(
                font_size=self.config.message_font_size,
                text_align='center',
                color=self.config.message_color,
            )
        )
        error_box.add(error_label)

        return error_box

    @staticmethod
    def create(message: str, config: Optional[ErrorScreenConfig] = None) -> toga.Box:
        """
        Static method to create error UI.
        
        Args:
            message: Error message to display
            config: Optional error screen configuration
            
        Returns:
            Toga Box containing the error UI
        """
        screen = ErrorScreen(config)
        return screen.create_ui(message)
