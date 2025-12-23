#!/usr/bin/env python3
import gi
import json
import os
import subprocess

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
gi.require_version("Wnck", "3.0")

from gi.repository import Gtk, WebKit2, Gdk, Wnck, GLib

class DesktopShell(Gtk.Window):
    def __init__(self):
        super().__init__(title="GoldenMoon Desktop env")
        self.set_decorated(False)
        self.fullscreen()

        # WebKit Settings for Local File Access and Security
        settings = WebKit2.Settings()
        settings.set_allow_universal_access_from_file_urls(True)
        settings.set_allow_file_access_from_file_urls(True)

        # JS-Python Bridge Setup
        self.content_manager = WebKit2.UserContentManager()
        self.content_manager.register_script_message_handler("bridge")
        self.content_manager.connect("script-message-received::bridge", self.on_js_message)

        # WebView Initialization
        self.webview = WebKit2.WebView.new_with_user_content_manager(self.content_manager)
        self.webview.set_settings(settings)
        
        # Load local HTML
        current_dir = os.path.dirname(os.path.realpath(__file__))
        html_path = "file://" + os.path.join(current_dir, "desktop.html")
        self.webview.load_uri(html_path)

        self.add(self.webview)
        self.connect("destroy", Gtk.main_quit)

        # Initialize Wnck for Window Tracking
        self.screen = Wnck.Screen.get_default()
        # Update running apps status every 2 seconds
        GLib.timeout_add_seconds(2, self.update_running_apps)

        self.show_all()

    def get_system_icon_path(self, icon_name):
        """Resolves system icon names to absolute file:// paths."""
        icon_theme = Gtk.IconTheme.get_default()
        icon_info = icon_theme.lookup_icon(icon_name, 48, 0)
        return "file://" + icon_info.get_filename() if icon_info else ""

    def update_running_apps(self):
        """Checks for open windows and tells JS which apps are running."""
        self.screen.force_update()
        # Get list of WM_CLASS names of all open windows
        running_windows = [w.get_class_group_name().lower() for w in self.screen.get_windows()]
        self.webview.run_javascript(f"updateRunningIndicators({json.dumps(running_windows)})")
        return True

    def on_js_message(self, manager, result):
        """Primary handler for JS bridge calls."""
        message = result.get_js_value().to_string()
        data = json.loads(message)
        action = data.get("action")

        if action == "get_dock_apps":
            self.handle_get_dock_apps()
        elif action == "launch_app":
            self.handle_launch_app(data.get("command"))
        elif action == "focus_app":
            self.handle_focus_app(data.get("command"))
        # Inside your on_js_message method in desktop.py
        elif action == "power_command":
            cmd = data.get("command")
            if cmd == "shutdown":
                subprocess.Popen(["systemctl", "poweroff"])
            elif cmd == "restart":
                subprocess.Popen(["systemctl", "reboot"])
            elif cmd == "sleep":
                subprocess.Popen(["systemctl", "suspend"])
        # Inside your on_js_message method in desktop.py
        elif action == "get_power_icons":
            icons = {
                "shutdown": self.get_system_icon_path("system-shutdown"),
                "restart": self.get_system_icon_path("system-reboot"),
                "sleep": self.get_system_icon_path("system-suspend") # or "weather-night"
            }
            self.webview.run_javascript(f"receivePowerIcons({json.dumps(icons)})")

    def handle_get_dock_apps(self):
        """Reads dock.json and sends it to the frontend with resolved icons."""
        try:
            with open("dock.json", "r") as f:
                apps = json.load(f)
            for app in apps:
                app['icon_path'] = self.get_system_icon_path(app['icon'])
            self.webview.run_javascript(f"receiveDockData({json.dumps(apps)})")
        except Exception as e:
            print(f"Error loading dock.json: {e}")

    def handle_launch_app(self, command):
        """Executes the app command."""
        try:
            subprocess.Popen(command.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.webview.run_javascript("onLaunchResult(true, '')")
        except Exception as e:
            self.webview.run_javascript(f"onLaunchResult(false, '{str(e)}')")

    def handle_focus_app(self, command):
        """Brings an already running window to the front."""
        self.screen.force_update()
        target = command.lower()
        for window in self.screen.get_windows():
            # Matches based on the window's group name (class)
            if target in window.get_class_group_name().lower():
                # FIXED: Using Gdk.CURRENT_TIME instead of the non-existent get_current_time()
                window.activate(Gdk.CURRENT_TIME)
                break

if __name__ == "__main__":
    DesktopShell()
    Gtk.main()