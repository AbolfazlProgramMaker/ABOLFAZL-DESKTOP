#!/usr/bin/env python3
import gi
import json
import os
import subprocess
import sys
import signal
import glob
import shutil
import logging

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

os.environ["WEBKIT_DISABLE_COMPOSITING_MODE"] = "1"

try:
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    try:
        gi.require_version("Wnck", "3.0")
    except ValueError:
        logging.warning("Wnck not available. Wayland might be in use.")
    try:
        gi.require_version("WebKit2", "4.1")
    except (ValueError, ImportError):
        gi.require_version("WebKit2", "4.0")
except ValueError as e:
    logging.error(f"Missing dependencies: {e}")
    sys.exit(1)

from gi.repository import Gtk, WebKit2, Gdk, Wnck, GLib

class DesktopShell(Gtk.Window):
    def __init__(self):
        super().__init__(title="ABOLFAZL-DESKTOP Shell")
        self.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
        self.set_decorated(False)
        self.set_keep_below(True)
        self.fullscreen()

        self.base_dir = os.path.dirname(os.path.realpath(__file__))
        self.config_file = os.path.join(self.base_dir, "config.json")

        self.screen = None
        self.init_screen()
        self.init_webview()
        self.show_all()

    def init_screen(self):
        try:
            self.screen = Wnck.Screen.get_default()
            if self.screen:
                self.screen.force_update()
                self.screen.connect("window-opened", lambda s, w: GLib.idle_add(self.update_running_apps))
                self.screen.connect("window-closed", lambda s, w: GLib.idle_add(self.update_running_apps))
                self.screen.connect("active-window-changed", lambda s, w: GLib.idle_add(self.update_running_apps))
        except Exception as e:
            logging.warning(f"Wnck init failed: {e}")
            self.screen = None

    def update_running_apps(self):
        if not self.screen:
            return False
        try:
            self.screen.force_update()
            windows = self.screen.get_windows()
            running_classes = list(set(
                (w.get_class_group_name() or "").lower()
                for w in windows
                if w and w.get_window_type() == Wnck.WindowType.NORMAL
            ))
            js_code = f"if(window.updateRunningIndicators) updateRunningIndicators({json.dumps(running_classes)});"
            self.run_js_safe(js_code)
        except Exception as e:
            logging.warning(f"Update running apps failed: {e}")
        return False

    def init_webview(self):
        try:
            self.content_manager = WebKit2.UserContentManager()
            self.content_manager.register_script_message_handler("bridge")
            self.content_manager.connect("script-message-received::bridge", self.on_js_message)

            settings = WebKit2.Settings()
            settings.set_allow_universal_access_from_file_urls(True)
            settings.set_allow_file_access_from_file_urls(True)
            settings.set_enable_developer_extras(True)

            self.webview = WebKit2.WebView.new_with_user_content_manager(self.content_manager)
            self.webview.set_settings(settings)
            self.webview.set_background_color(Gdk.RGBA(0,0,0,0))

            html_file = os.path.join(self.base_dir, "desktop.html")
            if os.path.exists(html_file):
                self.webview.load_uri("file://" + os.path.abspath(html_file))
            else:
                logging.error(f"{html_file} not found!")

            self.add(self.webview)
        except Exception as e:
            logging.error(f"WebView init failed: {e}")

    def run_js_safe(self, code):
        try:
            if hasattr(self, 'webview') and self.webview:
                self.webview.run_javascript(code, None, None, None)
        except Exception as e:
            logging.warning(f"JS execution failed: {e}")

    def on_js_message(self, manager, result):
        try:
            message = result.get_js_value().to_string()
            data = json.loads(message)
            action = data.get("action")
            if not action: return

            mapping = {
                "get_dock_apps": self.handle_get_dock_apps,
                "get_power_icons": self.send_power_icons,
                "open_bg_picker": self.handle_open_bg_picker,
                "get_saved_background": self.handle_get_saved_background,
                "launch_app": lambda: self.handle_launch_app(data.get("command")),
                "focus_app": lambda: self.handle_focus_app(data.get("command")),
                "power_command": lambda: self.handle_power_command(data.get("command"))
            }

            if action in mapping:
                mapping[action]()
        except Exception as e:
            logging.warning(f"Bridge error: {e}")

    def handle_power_command(self, cmd):
        commands = {
            "shutdown": ["systemctl","poweroff"],
            "restart": ["systemctl","reboot"],
            "sleep": ["systemctl","suspend"]
        }
        if cmd in commands:
            if shutil.which("systemctl"):
                try:
                    subprocess.Popen(commands[cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception as e:
                    logging.warning(f"Power command failed: {e}")
            else:
                logging.warning("systemctl not found. Power command skipped.")

    def send_power_icons(self):
        icons = {
            "shutdown": self.get_system_icon_path("system-shutdown"),
            "restart": self.get_system_icon_path("view-refresh"),
            "sleep": self.get_system_icon_path("system-suspend")
        }
        self.run_js_safe(f"if(window.receivePowerIcons) receivePowerIcons({json.dumps(icons)});")

    def handle_open_bg_picker(self):
        dialog = Gtk.FileChooserDialog(
            title="Select Wallpaper",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        )
        filter_img = Gtk.FileFilter()
        filter_img.set_name("Images")
        filter_img.add_pixbuf_formats()
        dialog.add_filter(filter_img)

        if dialog.run() == Gtk.ResponseType.OK:
            path = dialog.get_filename()
            try:
                os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
                with open(self.config_file, "w") as f:
                    json.dump({"wallpaper": path}, f)
                self.run_js_safe(f"if(window.applyBackground) applyBackground('file://{path}')")
            except Exception as e:
                logging.warning(f"Save config failed: {e}")
        dialog.destroy()

    def handle_get_saved_background(self):
        bg_path = None
        if os.path.exists(self.config_file):
            try:
                bg_path = json.load(open(self.config_file)).get("wallpaper")
                if bg_path: bg_path = "file://"+bg_path
            except Exception:
                pass
        self.run_js_safe(f"if(window.receiveSavedBackground) receiveSavedBackground({json.dumps(bg_path)})")

    def discover_installed_apps(self):
        apps = []
        paths = [
            "/usr/share/applications/*.desktop",
            os.path.expanduser("~/.local/share/applications/*.desktop")
        ]
        seen_execs = set()
        for pattern in paths:
            for file in glob.glob(pattern):
                try:
                    with open(file,"r", encoding="utf-8") as f:
                        content = f.read()
                    exec_lines = [line for line in content.splitlines() if line.startswith("Exec=")]
                    name_lines = [line for line in content.splitlines() if line.startswith("Name=")]
                    icon_lines = [line for line in content.splitlines() if line.startswith("Icon=")]

                    if not exec_lines or not name_lines:
                        continue

                    exec_cmd = exec_lines[0].split("=",1)[1].split()[0]
                    name = name_lines[0].split("=",1)[1]
                    icon_name = icon_lines[0].split("=",1)[1] if icon_lines else None

                    if exec_cmd and exec_cmd not in seen_execs and shutil.which(exec_cmd):
                        apps.append({
                            "id": exec_cmd.lower(),
                            "name": name,
                            "icon": icon_name,
                            "exec": exec_cmd,
                            "icon_path": self.get_system_icon_path(icon_name)
                        })
                        seen_execs.add(exec_cmd)
                except Exception as e:
                    logging.debug(f"Desktop parse failed for {file}: {e}")
        return apps

    def handle_get_dock_apps(self):
        apps = self.discover_installed_apps()
        self.run_js_safe(f"if(window.receiveDockData) receiveDockData({json.dumps(apps)})")

    def handle_launch_app(self, cmd):
        if cmd:
            try:
                subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                logging.warning(f"Launch failed: {e}")

    def handle_focus_app(self, cmd):
        if not self.screen: return
        self.screen.force_update()
        target = cmd.lower()
        for window in self.screen.get_windows():
            try:
                if window and target in (window.get_class_group_name() or "").lower():
                    window.activate(Gdk.CURRENT_TIME)
                    break
            except Exception:
                continue

    def get_system_icon_path(self, icon_name):
        if not icon_name: return ""
        try:
            theme = Gtk.IconTheme.get_default()
            icon_info = theme.lookup_icon(icon_name, 48, 0)
            if icon_info:
                return "file://" + icon_info.get_filename()
        except Exception as e:
            logging.debug(f"Icon lookup failed: {e}")
        return ""

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    Gtk.init(sys.argv)
    try:
        DesktopShell()
        Gtk.main()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
