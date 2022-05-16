#!/usr/bin/env python3
import sys
import os
import gi
import json
import codecs
import logging

from . import url_handler

gi.require_version('Gtk', '3.0')
from gi.repository import GObject, Gtk, GLib, GdkPixbuf, Gdk, Gio

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
# Important that APP_VERSION line has = "(num)" in so gitcommit script finds it
APP_VERSION = "1.60.32"
sv = os.environ.get("SNAP_VERSION")
if sv:
    APP_VERSION = f"{sv} (snap)"


LOGLEVEL = os.environ.get('LOGLEVEL', 'WARNING').upper()
logging.basicConfig(level=LOGLEVEL)


class UTMNOIndicator(GObject.GObject):
    def __init__(self):
        global APP_VERSION
        GObject.GObject.__init__(self)

        icon_path = None
        local_icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "icons"))
        if os.path.exists("/.flatpak-info"):
            # we're inside a flatpak
            # we need to use the real path, not the in-the-flatpak
            # path, so the panel can read it
            import configparser
            try:
                c = configparser.ConfigParser(interpolation=None)
                c.read("/.flatpak-info")
                real_fs_path = c.get('Instance', 'app-path', fallback=None)
                if real_fs_path:
                    icon_path = os.path.join(real_fs_path, "utm_no", "icons")
                    APP_VERSION = f"{APP_VERSION} (flatpak)"
            except Exception as e:
                logging.error(f"Tried to read /.flatpak-info but failed", e)
        if not icon_path:
            icon_path = local_icon_path
        self.panel_eyes_closed_icon = os.path.abspath(os.path.join(icon_path, "panel-eyes-full-closed.svg"))
        self.panel_eyes_left_icon = os.path.abspath(os.path.join(icon_path, "panel-eyes-left.svg"))
        self.panel_eyes_right_icon = os.path.abspath(os.path.join(icon_path, "panel-eyes-right.svg"))
        self.panel_eyes_half_right_icon = os.path.abspath(os.path.join(icon_path, "panel-eyes-half-right.svg"))
        self.panel_disabled_icon = os.path.abspath(os.path.join(icon_path, "panel-eyes-disabled.svg"))
        self.app_icon = os.path.abspath(os.path.join(local_icon_path, "utm_no.svg"))

        self.ind = AppIndicator.Indicator.new(
            APP_ID, self.panel_eyes_closed_icon,
            AppIndicator.IndicatorCategory.HARDWARE)
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.ind.set_title(APP_NAME)

        self.menu = Gtk.Menu()
        self.ind.set_menu(self.menu)

        self.mpaused = Gtk.CheckMenuItem.new_with_mnemonic("_Enabled")
        self.mpaused.set_active(True)  # set first so we don't call the handler
        self.mpaused.connect("toggled", self.toggle_enabled, None)
        self.mpaused.show()
        self.menu.append(self.mpaused)

        self.mtco = Gtk.CheckMenuItem.new_with_mnemonic("_Look up Twitter (t.co) links")
        self.mtco.set_active(False)  # set first so we don't call the handler
        self.mtco.connect("toggled", self.toggle_tco, None)
        # self.mtco.show() # don't show this menu item unless we've already asked about using it
        self.menu.append(self.mtco)

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

        self.fix_urls_in_text = True # hardcode this on for now; we fix URLs within copied text
        GLib.idle_add(self.load_config)

    def get_cache_file(self):
        return os.path.join(GLib.get_user_config_dir(), "utm_no.json")

    def serialise(self, *args, **kwargs):
        # yeah, yeah, supposed to use Gio's async file stuff here. But it was
        # writing corrupted files, and I have no idea why; probably the Python
        # var containing the data was going out of scope or something. Anyway,
        # we're only storing a small JSON file, so life's too short to hammer
        # on this; we'll write with Python and take the hit.
        fp = codecs.open(self.get_cache_file(), encoding="utf8", mode="w")
        data = {
            "enabled": self.mpaused.get_active(),
            "tco": {
                "enabled": self.mtco.get_active(),
                "asked": self.mtco.get_visible()
            }
        }
        json.dump(data, fp, indent=2)
        fp.close()
        logging.debug(f"Serialised {data}")

    def load_config(self):
        f = Gio.File.new_for_path(self.get_cache_file())
        f.load_contents_async(None, self.finish_loading_history)

    def finish_loading_history(self, f, res):
        try:
            success, contents, _ = f.load_contents_finish(res)
        except GLib.Error as e:
            logging.warning(
                f"couldn't restore settings (error: {e}), so assuming they're blank")
            contents = "{}"

        try:
            data = json.loads(contents)
        except Exception as e:
            logging.warning(
                f"Warning: settings file seemed to be invalid json (error: {e}), so assuming blank")
            data = {}
        self.mpaused.set_active(data.get("enabled", True))
        tco = data.get("tco", {})
        if tco.get("asked", False): self.mtco.show()
        if tco.get("enabled", False): self.mtco.set_active(True)

    def show_ask_tco_dialogue(self, clipboard, text):
        dialog = Gtk.MessageDialog(
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text="Look up Twitter 't.co' links?",
        )
        dialog.add_buttons(
            "Don't ping Twitter", Gtk.ResponseType.NO,
            "Look up t.co links", Gtk.ResponseType.YES)
        dialog.format_secondary_text(
            "This copied text contains a tracking link from Twitter (to a "
            "t.co URL).\n"
            "utm_no can look up these links to get the real URL so you don't "
            "paste the t.co tracking link.\n"
            "However, this means that Twitter "
            "will register a 'hit' from your IP address whenever you copy one "
            "of these links.\n\n"
            "This feature can be enabled or disabled in future from "
            "the indicator menu."
        )
        response = dialog.run()
        self.mtco.show()
        if response == Gtk.ResponseType.YES:
            self.mtco.set_active(True)
        elif response == Gtk.ResponseType.NO:
            self.mtco.set_active(False)
        self.serialise()
        dialog.destroy()
        if response == Gtk.ResponseType.YES:
            self.handleText(clipboard, text)

    def handleText(self, clipboard, text):
        if not self.mtco.get_visible() and url_handler.contains_tco(text):
            # this is the first time we've copied a t.co address
            # ask about whether to handle them
            self.show_ask_tco_dialogue(clipboard, text)
            return
        handle_tco = self.mtco.get_active()
        if url_handler.is_url(text.strip()):
            # if the text is nothing but a URL, handle it always
            new_text = url_handler.fix_text(text, handle_tco=handle_tco)
        elif self.fix_urls_in_text:
            # if the setting is on, process the whole text and handle all URLs within it
            new_text = url_handler.fix_text(text, handle_tco=handle_tco)
        else:
            return text
        if new_text == text:
            return text

        # The text has been changed, set it on the clipboard and flash the icon
        clipboard.set_text(new_text, -1)
        logging.debug(f"Overridden clipboard contents to {repr(new_text)}")
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
        GLib.idle_add(self.serialise)

    def toggle_tco(self, widget, *args):
        GLib.idle_add(self.serialise)

    def quit(self, *args):
        GLib.timeout_add(100, lambda *args: Gtk.main_quit())

    def show_about(self, *args):
        dialog = Gtk.AboutDialog()
        dialog.set_program_name(APP_NAME)
        dialog.set_copyright('Stuart Langridge')
        dialog.set_license(APP_LICENCE)
        dialog.set_version(APP_VERSION)
        dialog.set_website('https://kryogenix.org/code/utm_no')
        dialog.set_website_label('kryogenix.org/code/utm_no')
        dialog.set_comments("Remove tracking parameters from copied links")
        dialog.set_logo(GdkPixbuf.Pixbuf.new_from_file_at_size(self.app_icon, 64, 64))
        dialog.connect('response', lambda *largs: dialog.destroy())
        dialog.run()

    @staticmethod
    def run():
        Gtk.main()


if __name__ == "__main__":
    UTMNOIndicator().run()
