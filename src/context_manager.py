# src/context_manager.py

import sys
import psutil
import logging
import pygetwindow as gw

# --- NEW: Add Windows-specific imports for a more reliable PID lookup ---
if sys.platform == "win32":
    import win32process
    import win32gui

logger = logging.getLogger(__name__)


class ContextManager:
    """Monitors the user's active window and application."""

    def get_active_window_info(self) -> tuple[str | None, str | None]:
        """
        Gets the title and process name of the currently active window.
        Uses a more robust method for Windows to get the Process ID.
        """
        try:
            active_window = gw.getActiveWindow()
            if not active_window:
                return (None, None)

            window_title: str | None = active_window.title
            pid = None

            # --- NEW: Robust PID lookup for Windows ---
            if sys.platform == "win32":
                try:
                    # _hWnd is the window handle, which is what we need
                    hwnd = active_window._hWnd
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                except Exception as e:
                    logger.warning(f"Could not get PID via win32 API: {e}")
            # --- END NEW ---

            # If we have a PID, get the process name
            if pid:
                p = psutil.Process(pid)
                process_name: str | None = p.name().lower()
                return (window_title, process_name)
            
            # Fallback for non-windows or if the above failed
            logger.debug("Could not determine PID directly, falling back to title matching.")
            return (window_title, None)

        except (gw.PyGetWindowException, psutil.NoSuchProcess, psutil.AccessDenied) as e:
            # These are expected errors if a window closes suddenly, so we log as debug.
            logger.debug(f"Could not get active window info: {e}")
            return (None, None)
        except Exception as e:
            logger.error(f"An unexpected error occurred in ContextManager: {e}", exc_info=True)
            return (None, None)