#!/usr/bin/env python3
import gi
import json
import os
import subprocess
import sys  # Added for Gdk arguments

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
gi.require_version("Gdk", "3.0")
gi.require_version("Wnck", "3.0")

from gi.repository import Gtk, WebKit2, Gdk, Wnck, GLib

class DesktopShell(Gtk.Window):
    def __init__(self):
        super().__init__(title="GoldenMoon Desktop Shell")
        
        # Desktop window properties
        self.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
        self.set_decorated(False)
        self.set_keep_below(True)
        self.fullscreen()

        # Path management
        self.base_dir = os.path.dirname(os.path.realpath(__file__))
        self.config_file = os.path.join(self.base_dir, "config.json")
        self.dock_file = os.path.join(self.base_dir, "dock.json")

        # WebKit Setup
        settings = WebKit2.Settings()
        settings.set_allow_universal_access_from_file_urls(True)
        settings.set_allow_file_access_from_file_urls(True)

        self.content_manager = WebKit2.UserContentManager()
        self.content_manager.register_script_message_handler("bridge")
        self.content_manager.connect("script-message-received::bridge", self.on_js_message)

        self.webview = WebKit2.WebView.new_with_user_content_manager(self.content_manager)
        self.webview.set_settings(settings)
        self.webview.set_background_color(Gdk.RGBA(0, 0, 0, 1))
        
        html_path = "file://" + os.path.join(self.base_dir, "desktop.html")
        self.webview.load_uri(html_path)

        self.add(self.webview)
        self.connect("destroy", Gtk.main_quit)

        # Window Management via Wnck Signals (Event-driven)
        self.screen = Wnck.Screen.get_default()
        
        # Use idle_add to prevent reentrancy_guard errors (Wnck-CRITICAL fix)
        self.screen.connect("window-opened", lambda s, w: GLib.idle_add(self.update_running_apps))
        self.screen.connect("window-closed", lambda s, w: GLib.idle_add(self.update_running_apps))
        self.screen.connect("active-window-changed", lambda s, w: GLib.idle_add(self.update_running_apps))

        self.show_all()

    def get_system_icon_path(self, icon_name):
        if not icon_name: return ""
        icon_theme = Gtk.IconTheme.get_default()
        icon_info = icon_theme.lookup_icon(icon_name, 48, 0)
        return "file://" + icon_info.get_filename() if icon_info else ""

    def update_running_apps(self):
        """Updates the UI based on currently open windows."""
        self.screen.force_update()
        windows = self.screen.get_windows()
        running_classes = list(set(
            w.get_class_group_name().lower() 
            for w in windows 
            if w.get_window_type() == Wnck.WindowType.NORMAL
        ))
        
        json_data = json.dumps(running_classes)
        js_code = f"if(window.updateRunningIndicators) updateRunningIndicators({json_data});"
        
        # Updated method to fix DeprecationWarning
        self.webview.run_javascript(js_code, None, None, None)
        return False  # Required for GLib compatibility when called via idle_add

    def on_js_message(self, manager, result):
        try:
            message = result.get_js_value().to_string()
            data = json.loads(message)
            action = data.get("action")

            if action == "get_dock_apps":
                self.handle_get_dock_apps()
            elif action == "launch_app":
                self.handle_launch_app(data.get("command"))
            elif action == "focus_app":
                self.handle_focus_app(data.get("command"))
            elif action == "power_command":
                self.handle_power_command(data.get("command"))
            elif action == "get_power_icons":
                self.send_power_icons()
            elif action == "open_bg_picker":
                self.handle_open_bg_picker()
            elif action == "get_saved_background":
                self.handle_get_saved_background()
        except Exception as e:
            print(f"Bridge Error: {e}")

    def handle_power_command(self, cmd):
        cmds = {
            "shutdown": ["systemctl", "poweroff"],
            "restart": ["systemctl", "reboot"],
            "sleep": ["systemctl", "suspend"]
        }
        if cmd in cmds:
            subprocess.Popen(cmds[cmd])

    def send_power_icons(self):
        icons = {
            "shutdown": self.get_system_icon_path("system-shutdown"),
            "restart": self.get_system_icon_path("view-refresh"),
            "sleep": self.get_system_icon_path("system-suspend")
        }
        self.webview.run_javascript(f"if(window.receivePowerIcons) receivePowerIcons({json.dumps(icons)});", None, None, None)

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
            with open(self.config_file, "w") as f:
                json.dump({"wallpaper": path}, f)
            self.webview.run_javascript(f"applyBackground('file://{path}')", None, None, None)
        dialog.destroy()

    def handle_get_saved_background(self):
        bg_path = None
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    bg_path = "file://" + json.load(f).get("wallpaper")
            except: pass
        self.webview.run_javascript(f"receiveSavedBackground({json.dumps(bg_path)});", None, None, None)

    def handle_get_dock_apps(self):
        if os.path.exists(self.dock_file):
            with open(self.dock_file, "r") as f:
                apps = json.load(f)
                for app in apps:
                    app['icon_path'] = self.get_system_icon_path(app.get('icon'))
                self.webview.run_javascript(f"receiveDockData({json.dumps(apps)});", None, None, None)

    def handle_launch_app(self, cmd):
        if cmd:
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def handle_focus_app(self, cmd):
        self.screen.force_update()
        target = cmd.lower()
        for window in self.screen.get_windows():
            if target in window.get_class_group_name().lower():
                window.activate(Gdk.CURRENT_TIME)
                break

if __name__ == "__main__":
    # Passing sys.argv instead of None to fix TypeError
    Gdk.init(sys.argv)
    DesktopShell()
    Gtk.main()
    