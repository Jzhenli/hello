"""Splash screen UI component."""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
from typing import Optional

from ..config import SplashConfig


class SplashScreen:
    """Splash screen with progress indicator."""

    def __init__(self, config: SplashConfig = None):
        self.config = config or SplashConfig()
        self.progress_bar = None
        self.status_label = None
        self.step_labels = []

    def create_ui(self) -> toga.Box:
        """
        Create the splash screen UI.
        
        Returns:
            Toga Box containing the splash UI
        """
        main_box = toga.Box(
            style=Pack(
                direction=COLUMN,
                align_items='center',
                margin=40,
                flex=1,
            )
        )

        title_label = toga.Label(
            self.config.title,
            style=Pack(
                font_size=28,
                font_weight='bold',
                margin_bottom=8,
                text_align='center',
            )
        )
        main_box.add(title_label)

        subtitle_label = toga.Label(
            self.config.subtitle,
            style=Pack(
                font_size=14,
                margin_bottom=40,
                text_align='center',
                color='#666666',
            )
        )
        main_box.add(subtitle_label)

        self.progress_bar = toga.ProgressBar(
            max=100,
            value=0,
            style=Pack(
                width=400,
                margin_bottom=20,
            )
        )
        main_box.add(self.progress_bar)

        self.status_label = toga.Label(
            "Initializing...",
            style=Pack(
                font_size=13,
                margin_bottom=30,
                text_align='center',
                color='#444444',
            )
        )
        main_box.add(self.status_label)

        steps_box = toga.Box(
            style=Pack(
                direction=ROW,
                align_items='center',
                margin_top=10,
            )
        )

        steps_to_display = self.config.steps[:-1]
        for i, step in enumerate(steps_to_display):
            step_label = toga.Label(
                step.name,
                style=Pack(
                    font_size=11,
                    margin_left=8,
                    margin_right=8,
                    color='#999999',
                )
            )
            self.step_labels.append(step_label)
            steps_box.add(step_label)

            if i < len(steps_to_display) - 1:
                separator = toga.Label(
                    "→",
                    style=Pack(
                        font_size=11,
                        color='#cccccc',
                    )
                )
                steps_box.add(separator)

        main_box.add(steps_box)

        version_label = toga.Label(
            f"v{self.config.version}",
            style=Pack(
                font_size=10,
                margin_top=40,
                text_align='center',
                color='#aaaaaa',
            )
        )
        main_box.add(version_label)

        return main_box

    def update_progress(self, step_index: int, status_text: str = None) -> None:
        """
        Update progress bar and status.
        
        Args:
            step_index: Index of the current step
            status_text: Optional custom status text
        """
        if step_index < len(self.config.steps):
            step = self.config.steps[step_index]
            self.progress_bar.value = step.progress

            for i, label in enumerate(self.step_labels):
                if i < step_index:
                    label.style.color = '#28a745'
                elif i == step_index:
                    label.style.color = '#007bff'
                else:
                    label.style.color = '#999999'

        if status_text:
            self.status_label.text = status_text
        else:
            if step_index < len(self.config.steps):
                self.status_label.text = self.config.steps[step_index].name
            else:
                self.status_label.text = "Done"
