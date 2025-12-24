#!/usr/bin/env python3
import gi
import json
import os
import subprocess

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
gi.require_version("Gdk", "3.0")
gi.require_version("Wnck", "3.0")

from gi.repository import Gtk, WebKit2, Gdk, Wnck, GLib

class DesktopShell(Gtk.Window):
    def __init__(self):
        super().__init__(title="GoldenMoon Desktop env")
        self.set_decorated(False)
        self.fullscreen()

        settings = WebKit2.Settings()
        settings.set_allow_universal_access_from_file_urls(True)
        settings.set_allow_file_access_from_file_urls(True)

        self.content_manager = WebKit2.UserContentManager()
        self.content_manager.register_script_message_handler("bridge")
        self.content_manager.connect("script-message-received::bridge", self.on_js_message)

        self.webview = WebKit2.WebView.new_with_user_content_manager(self.content_manager)
        self.webview.set_settings(settings)
        
        current_dir = os.path.dirname(os.path.realpath(__file__))
        html_path = "file://" + os.path.join(current_dir, "desktop.html")
        self.webview.load_uri(html_path)

        self.add(self.webview)
        self.connect("destroy", Gtk.main_quit)

        self.screen = Wnck.Screen.get_default()
        GLib.timeout_add_seconds(2, self.update_running_apps)
        self.show_all()

    def get_system_icon_path(self, icon_name):
        icon_theme = Gtk.IconTheme.get_default()
        icon_info = icon_theme.lookup_icon(icon_name, 48, 0)
        return "file://" + icon_info.get_filename() if icon_info else ""

    def update_running_apps(self):
        self.screen.force_update()
        running_windows = [w.get_class_group_name().lower() for w in self.screen.get_windows()]
        self.webview.run_javascript(f"updateRunningIndicators({json.dumps(running_windows)})")
        return True

    def on_js_message(self, manager, result):
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
            cmd = data.get("command")
            if cmd == "shutdown": subprocess.Popen(["systemctl", "poweroff"])
            elif cmd == "restart": subprocess.Popen(["systemctl", "reboot"])
            elif cmd == "sleep": subprocess.Popen(["systemctl", "suspend"])
        elif action == "get_power_icons":
            icons = {
                "shutdown": self.get_system_icon_path("system-shutdown"),
                "restart": self.get_system_icon_path("system-reboot"),
                "sleep": self.get_system_icon_path("system-suspend")
            }
            self.webview.run_javascript(f"receivePowerIcons({json.dumps(icons)})")
        
        # --- NEW BACKGROUND ACTIONS ---
        elif action == "open_bg_picker":
            self.handle_open_bg_picker()
        elif action == "get_saved_background":
            self.handle_get_saved_background()

    def handle_open_bg_picker(self):
        """Opens a native GTK file picker to select an image."""
        dialog = Gtk.FileChooserDialog(
            title="Select Wallpaper",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        )
        
        # Filter for images only
        filter_img = Gtk.FileFilter()
        filter_img.set_name("Image files")
        filter_img.add_mime_type("image/png")
        filter_img.add_mime_type("image/jpeg")
        filter_img.add_pattern("*.jpg")
        filter_img.add_pattern("*.png")
        dialog.add_filter(filter_img)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            file_path = dialog.get_filename()
            # Save to JSON
            with open("config.json", "w") as f:
                json.dump({"wallpaper": file_path}, f)
            # Update UI immediately
            self.webview.run_javascript(f"applyBackground('file://{file_path}')")
        
        dialog.destroy()

    def handle_get_saved_background(self):
        """Reads config.json. If it doesn't exist, sends null to JS."""
        saved_path = None
        config_file = "config.json"
        
        if os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    data = json.load(f)
                    path = data.get("wallpaper")
                    if path and os.path.exists(path):
                        # Convert absolute path to file:// for WebKit
                        saved_path = "file://" + path
            except Exception as e:
                print(f"Error reading config: {e}")
        
        # If saved_path is None, JS receiveSavedBackground will use wallpaper.png
        self.webview.run_javascript(f"receiveSavedBackground({json.dumps(saved_path)})")

    def handle_get_dock_apps(self):
        try:
            with open("dock.json", "r") as f:
                apps = json.load(f)
            for app in apps:
                app['icon_path'] = self.get_system_icon_path(app['icon'])
            self.webview.run_javascript(f"receiveDockData({json.dumps(apps)})")
        except Exception as e:
            print(f"Error loading dock.json: {e}")

    def handle_launch_app(self, command):
        try:
            subprocess.Popen(command.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except: pass

    def handle_focus_app(self, command):
        self.screen.force_update()
        target = command.lower()
        for window in self.screen.get_windows():
            if target in window.get_class_group_name().lower():
                window.activate(Gdk.CURRENT_TIME)
                break

if __name__ == "__main__":
    DesktopShell()
    Gtk.main()