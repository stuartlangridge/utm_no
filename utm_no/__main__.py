#!/usr/bin/env python3
import sys
import os
import gi

from . import url_handler

gi.require_version('Gtk', '3.0')
from gi.repository import GObject, Gtk, GLib, GdkPixbuf, Gdk

gi.require_version('AppIndicator3', '0.1')
from gi.repository import AppIndicator3 as AppIndicator

APP_ID = 'utm_no'
APP_NAME = 'utm_no'
APP_LICENCE = """
MIT License

Copyright (c) 2021 Stuart Langridge

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""
APP_VERSION = os.environ.get("SNAP_VERSION", "latest")


class UTMNOIndicator(GObject.GObject):
    def __init__(self):
        GObject.GObject.__init__(self)

        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "icons"))
        self.panel_eyes_closed_icon = os.path.abspath(os.path.join(icon_path, "panel-eyes-closed.svg"))
        self.panel_eyes_left_icon = os.path.abspath(os.path.join(icon_path, "panel-eyes-left.svg"))
        self.panel_eyes_right_icon = os.path.abspath(os.path.join(icon_path, "panel-eyes-right.svg"))
        self.panel_eyes_half_right_icon = os.path.abspath(os.path.join(icon_path, "panel-eyes-half-right.svg"))
        self.panel_disabled_icon = os.path.abspath(os.path.join(icon_path, "panel-eyes-disabled.svg"))
        self.app_icon = os.path.abspath(os.path.join(icon_path, "utm_no.svg"))

        self.ind = AppIndicator.Indicator.new(
            APP_ID, self.panel_eyes_closed_icon,
            AppIndicator.IndicatorCategory.HARDWARE)
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.ind.set_title(APP_NAME)

        self.menu = Gtk.Menu()
        self.ind.set_menu(self.menu)

        self.mpaused = Gtk.CheckMenuItem.new_with_mnemonic("_Enabled")
        self.mpaused.connect("toggled", self.toggle_enabled, None)
        self.mpaused.set_active(True)
        self.mpaused.show()
        self.menu.append(self.mpaused)

        mabout = Gtk.MenuItem.new_with_mnemonic("_About")
        mabout.connect("activate", self.show_about, None)
        mabout.show()
        self.menu.append(mabout)

        mquit = Gtk.MenuItem.new_with_mnemonic("_Quit")
        mquit.connect("activate", self.quit, None)
        mquit.show()
        self.menu.append(mquit)

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.connect('owner-change', self.clipboardChanged)
        # don't monitor PRIMARY selection, the middle-click clipboard
        # primary = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
        # primary.connect('owner-change', clipboardChanged)

    def handleText(self, clipboard, text):
        if url_handler.is_url(text.strip()):
            # if the text is nothing but a URL, handle it always
            new_text = url_handler.fix_text(text)
        elif False:
            # if the setting is on, process the whole text and handle all URLs within it
            new_text = url_handler.fix_text(text)
        else:
            return text
        if new_text == text:
            return text

        # The text has been changed, set it on the clipboard and flash the icon
        clipboard.set_text(new_text, -1)
        print("Overridden clipboard contents to", repr(new_text))
        self.animate_icon()

    def animate_icon(self, step=0):
        STEPS = [
            self.panel_eyes_right_icon,
            self.panel_eyes_half_right_icon,
            self.panel_eyes_closed_icon,
            self.panel_eyes_left_icon
        ]
        # if we're done, bail without recursively going on to the next step
        if step >= len(STEPS):
            self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
            return
        self.ind.set_attention_icon_full(STEPS[step], f"{APP_NAME} altering clipboard")
        if step == 0:
            self.ind.set_status(AppIndicator.IndicatorStatus.ATTENTION)
        GLib.timeout_add(150, self.animate_icon, step + 1)

    def clipboardChanged(self, clipboard, owner_change):
        if not self.mpaused.get_active(): return
        # This should not infinitely loop, because we don't set the text
        # unless we changed it, and if we changed it, it won't need
        # changing again, so we won't set it a second time.
        if clipboard.wait_is_text_available():
            data = clipboard.wait_for_text()
            if data:
                ndata = data + ""  # cast to string
                self.handleText(clipboard, ndata)

    def toggle_enabled(self, widget, *args):
        if widget.get_active():
            self.ind.set_icon_full(self.panel_eyes_closed_icon, f"{APP_NAME} running")
        else:
            self.ind.set_icon_full(self.panel_disabled_icon, f"{APP_NAME} disabled")

    def quit(self, *args):
        GLib.timeout_add(100, lambda *args: Gtk.main_quit())

    def show_about(self, *args):
        dialog = Gtk.AboutDialog()
        dialog.set_program_name(APP_NAME)
        dialog.set_copyright('Stuart Langridge')
        dialog.set_license(APP_LICENCE)
        dialog.set_version(APP_VERSION)
        dialog.set_website('https://kryogenix.org/code/utm_no')
        dialog.set_website_label('kryogenix.org')
        dialog.set_comments("Remove tracking parameters from copied links")
        dialog.set_logo(GdkPixbuf.Pixbuf.new_from_file(self.app_icon))
        dialog.connect('response', lambda *largs: dialog.destroy())
        dialog.run()

    @staticmethod
    def run():
        Gtk.main()


if __name__ == "__main__":
    UTMNOIndicator().run()
