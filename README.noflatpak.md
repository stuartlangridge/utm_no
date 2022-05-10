# Why utm_no isn't in Flathub

There isn't a flatpak of utm_no.

Sorry about that.

I did try to make one, but unfortunately it's somewhere between difficult and impossible to do for me as desktops are currently designed. This is because utm_no's interface is a system tray icon, and that's it, and system tray icons are difficult at best and maybe impossible to support in a flatpak as things currently stand.

## Why is it hard?

Basically, if you want a system tray icon in a Python Gtk app on Linux, you use AppIndicator3 (sometimes called AyatanaAppIndicator3). This is an old library, which was I assume originally built by the Ubuntu team as part of the Ayatana appindicators initiative, and a fork (the aforementioned AyatanaAppIndicator3) is now maintained as a community project.

(Maybe it's not called the system tray. Maybe it's the notification area. Maybe it should be called the panel. Maybe they're indicators. I do not intend to be rigorous about this, and I'll ignore complaints founded on how I've named this wrongly.)

The way AppIndicator3 works is that you create an icon by passing it an icon name. This can be a full path to an icon, and it works, so you can create a tray icon approximately like this:

```python
ind = AppIndicator3.Indicator.new("myapp", "/path/to/icon.svg",
                                  AI.IndicatorCategory.HARDWARE);
```

This is approximately what utm_no does.

Unfortunately, in a flatpak, that `/path/to/icon.svg` is _inside the flatpak sandbox_, where it's only accessible to other stuff inside the flatpak sandbox... and your top panel is _not_ inside the sandbox. AppIndicator3 doesn't actually create the icon itself; in essence, it's a library for talking to the thing which runs your panel, and _that thing_ creates the icon on your behalf. But that thing is the shell -- gnome shell, or KDE, or whatever. It's not inside the flatpak sandbox. So the file path you give it, which is a file path pointing to something inside your flatpak, is not available to that shell, and so... you don't get an icon.

## Why does AppIndicator3 only work with filenames and not allow you to pass a Pixbuf?

I don't know. I didn't design it. It doesn't work, though; [check out some docs](https://lazka.github.io/pgi-docs/AyatanaAppIndicator3-0.1/classes/Indicator.html). There's no way to pass a pixbuf; all you can do is hand it icon names. Now, _maaaaaaybe_ this would be OK if you're passing the name of an icon certain to be in the icon theme, which will be present outside the sandbox (although this is an extremely dubious assumption!) but utm_no doesn't do that; it uses custom icons.

## Why does utm_no use a system tray icon? Apps presenting a system tray icon as their UI are a violation of everything that is sacred about design!

No they aren't.

Some people in the Gnome project seem to think they are, certainly, and this contributed a little to me not pushing too hard to make a flatpak, since I assume that utm_no doesn't show anything in a stock Gnome desktop anyway (I don't know, I haven't checked). But Ubuntu, which is where the users mostly are, still supports system tray icons, as does pretty much every non-Linux OS; macOS does it, Windows does it, Android does it. And it makes sense for utm_no. It has very little actual _UI_; it uses a system tray icon because it should have _something_ on the screen which briefly indicates when it's cleansed a URL which has been copied to the clipboard. This does not need to be a very obvious indication -- it's deliberately designed to be unobtrusive, to show if at all only in your peripheral vision -- but it should be there. This should not be hidden away in a widget on some invisible widget overlay, or in a window which isn't showing; the whole point is that you'll see when something happens. That's what the system tray is for. In theory it could hide its system tray icon all the time and only show it when it cleans the clipboard, but that doesn't actually solve this problem, and it would look more obtrusive because everything else would jump in position.

The app also uses the tray icon to provide a way to get at its minimal configuration, but that's not what the tray icon is for, and the preferences could be moved to a preferences app or similar if need be. The icon is there so you get a peripheral notification that it worked. A popup notification would be way too obtrusive, and you would have no way of knowing that utm_no was even running.

## How does it work in the snap, then?

I don't know that either. Good question.

## Why not use something other than AppIndicator3?

I don't think there _is_ anything. There's [pystray](https://pystray.readthedocs.io/en/latest/usage.html#creating-the-menu) but that doesn't support menus under X at all, and that's it. There isn't a core Gtk way to do this, really, because Gnome doesn't want you to have system tray icons, which is why (Ayatana)AppIndicator3 has stuck around for so long. I could talk to org.kde.StatusNotifierWatcher's dbus API myself, but that's not something else, that's "reimplement AppIndicator3", which I'm not interested in doing and possibly am not able to do. And there's a [freedesktop discussion](https://gitlab.freedesktop.org/xdg/xdg-specs/-/issues/84) about making the next great indicator spec which will replace all the previous ones, which maybe I can use when everyone supports it, including all the people running past versions of Ubuntu where utm_no works fine.

However, the idea of using something else is the best way I can think for utm_no to be a flatpak. So, if you'd like that, or are interested in helping, then if you can tell me how to, from Python, inside a flatpak, create a system tray icon with icon data from inside the flatpak, then I am interested in listening!
