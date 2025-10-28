"""Cross-platform clipboard operations."""
import subprocess
import platform
import os


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard using system clipboard command.

    Args:
        text: Text to copy to clipboard

    Returns:
        bool: True if successful, False otherwise
    """
    # macOS: use pbcopy (built-in)
    if platform.system() == "Darwin":
        try:
            subprocess.run(['pbcopy'], input=text.encode(), check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    # Linux: For Wayland systems
    elif os.environ.get('XDG_SESSION_TYPE') == 'wayland':
        try:
            subprocess.run(['wl-copy'], input=text.encode(), check=True)
            print("Copied to clipboard using wl-copy")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("wl-copy not found. Install with: sudo pacman -S wl-clipboard")
            return False

    # Linux: For X11 systems
    else:
        try:
            subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode(), check=True)
            print("Copied to clipboard using xclip")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("xclip not found. Install with: sudo pacman -S xclip")
            return False
