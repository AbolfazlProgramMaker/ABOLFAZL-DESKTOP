#!/usr/bin/env python3
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")

from gi.repository import Gtk, WebKit2, Gdk

class DesktopShell(Gtk.Window):
    def __init__(self):
        super().__init__(title="GoldenMoon Desktop env")

        # Remove decorations
        self.set_decorated(False)

        # Make fullscreen
        self.fullscreen()

        # Set type hint to normal so it shows in taskbar
        self.set_type_hint(Gdk.WindowTypeHint.NORMAL)
        self.set_skip_taskbar_hint(False)  # show in taskbar
        self.set_skip_pager_hint(False)    # show in pager/workspace switcher

        # Enable transparent background if needed
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

        # Load HTML desktop
        webview = WebKit2.WebView()
        webview.load_uri("file://" + __file__.replace("desktop.py", "desktop.html"))

        self.add(webview)
        self.connect("destroy", Gtk.main_quit)
        self.show_all()

if __name__ == "__main__":
    DesktopShell()
    Gtk.main()
