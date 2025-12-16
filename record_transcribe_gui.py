"""Flet GUI for RecordTranscribe.

A modern cross-platform GUI for voice recording and transcription.
"""
import flet as ft
import threading
from src.models import create_stt_provider, create_cleanup_provider
from src.config import Settings, TranscriptionHistory
from src.core.audio_recorder import AudioRecorder
from src.core.clipboard import copy_to_clipboard


class RecordTranscribeApp:
    """Main GUI application."""

    def __init__(self, page: ft.Page):
        """Initialize the application.

        Args:
            page: Flet page instance
        """
        self.page = page
        self.page.title = "RecordTranscribe"
        self.page.window_width = 500
        self.page.window_height = 600
        self.page.window_resizable = False

        # Initialize settings and history
        self.settings = Settings()
        self.history = TranscriptionHistory(max_items=self.settings.get("history_max_items", 50))

        # Initialize models (this will take a moment)
        self.status_text = ft.Text("Loading models...", size=14, color="gray")
        self.page.add(ft.Container(
            content=self.status_text,
            padding=20,
            alignment=ft.alignment.center
        ))
        self.page.update()

        # Load models in background
        threading.Thread(target=self._init_models, daemon=True).start()

    def _init_models(self):
        """Initialize STT and cleanup models (runs in background thread)."""
        try:
            # Create providers
            self.stt_provider = create_stt_provider()
            self.cleanup_provider = create_cleanup_provider(
                enable=self.settings.cleanup_enabled
            )

            # Create audio recorder wrapper (simplified - using existing core)
            # We'll integrate this properly with the GUI state
            self.recorder = None  # Will be initialized when needed

            # Update UI on main thread
            self.page.run_thread_safe(self._build_ui)

        except Exception as e:
            error_msg = f"Error loading models: {e}"
            self.page.run_thread_safe(lambda: self._show_error(error_msg))

    def _build_ui(self):
        """Build the main UI (called after models load)."""
        self.page.clean()

        # Status indicator
        self.status_icon = ft.Icon(ft.icons.MIC, size=80, color="gray")
        self.status_text = ft.Text("Ready to record", size=16, weight="bold")
        self.status_detail = ft.Text(
            f"STT: {self.stt_provider.get_backend_name()}",
            size=12,
            color="gray"
        )

        status_container = ft.Container(
            content=ft.Column([
                self.status_icon,
                self.status_text,
                self.status_detail,
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            padding=30,
            alignment=ft.alignment.center
        )

        # Control buttons
        self.record_button = ft.ElevatedButton(
            "Start Recording",
            icon=ft.icons.MIC,
            on_click=self._toggle_recording,
            width=200,
            height=50
        )

        controls_container = ft.Container(
            content=ft.Column([
                self.record_button,
                ft.Text(
                    f"Hotkey: {self.settings.hotkey} (CLI)",
                    size=10,
                    color="gray"
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
            padding=20,
            alignment=ft.alignment.center
        )

        # Recent transcriptions
        self.history_list = ft.ListView(spacing=5, padding=10, height=200)
        self._update_history_list()

        history_container = ft.Container(
            content=ft.Column([
                ft.Text("Recent Transcriptions", size=14, weight="bold"),
                ft.Divider(),
                self.history_list
            ]),
            padding=10
        )

        # Add all to page
        self.page.add(
            status_container,
            controls_container,
            history_container
        )
        self.page.update()

    def _toggle_recording(self, e):
        """Toggle recording state."""
        ft.Text("Recording functionality coming soon!")
        # TODO: Integrate with AudioRecorder
        # This requires careful threading to avoid blocking the UI

    def _update_history_list(self):
        """Update the history list display."""
        self.history_list.controls.clear()

        recent = self.history.get_recent(5)
        if not recent:
            self.history_list.controls.append(
                ft.Text("No transcriptions yet", size=12, italic=True, color="gray")
            )
        else:
            for item in recent:
                # Truncate text
                text = item["text"]
                if len(text) > 50:
                    text = text[:50] + "..."

                self.history_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(
                                ft.icons.CHECK_CIRCLE if item["cleanup_used"] else ft.icons.CIRCLE,
                                size=16,
                                color="green" if item["cleanup_used"] else "gray"
                            ),
                            ft.Text(text, size=12, expand=True),
                            ft.IconButton(
                                icon=ft.icons.COPY,
                                icon_size=16,
                                tooltip="Copy",
                                on_click=lambda e, t=item["text"]: self._copy_text(t)
                            )
                        ]),
                        padding=5,
                        border=ft.border.all(1, "gray"),
                        border_radius=5
                    )
                )

    def _copy_text(self, text: str):
        """Copy text to clipboard."""
        if copy_to_clipboard(text):
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Copied to clipboard!")))
        else:
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Clipboard unavailable")))

    def _show_error(self, message: str):
        """Show error message."""
        self.page.clean()
        self.page.add(
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.icons.ERROR, size=60, color="red"),
                    ft.Text("Error", size=20, weight="bold"),
                    ft.Text(message, size=12, color="gray", text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                padding=40,
                alignment=ft.alignment.center
            )
        )
        self.page.update()


def main(page: ft.Page):
    """Main entry point for Flet app."""
    RecordTranscribeApp(page)


if __name__ == "__main__":
    ft.app(target=main)
