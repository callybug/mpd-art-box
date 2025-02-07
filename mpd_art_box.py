#!/usr/bin/env python
import contextlib
import os
import pathlib
import threading
import time

import configargparse
import gi
import mpd

gi.require_version('Gtk', '3.0')

from gi.repository import Gio, GLib, Gtk, Gdk, GdkPixbuf  # noqa: E402

version = '0.0.9rnh (really naff hack)'


@contextlib.contextmanager
def _mpd_client(*args, **kwargs):
    attempts = 3
    for attempt in range(1, attempts + 1):
        try:
            client = mpd.MPDClient()
            client.connect(*args, **kwargs)
            break
        except ConnectionRefusedError:
            if attempt == attempts:
                raise
            else:
                time.sleep(1)
    try:
        yield client
    finally:
        client.disconnect()


def app_main(mpd_host, mpd_port, background_color):
    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(
        f'* {{ background-color: {background_color}; }}'.encode())
    context = Gtk.StyleContext()
    screen = Gdk.Screen.get_default()

    context.add_provider_for_screen(screen, css_provider,
                                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    win = Gtk.Window(default_height=500, default_width=500)

    win.connect('destroy', Gtk.main_quit)

    image = Gtk.Image()
    pixbuf = None
    win_size = None
    win.add(image)

    def set_image():
        nonlocal pixbuf
        nonlocal win_size
        image.clear()
        if pixbuf:
            win_size = win.get_size()
            win_width, win_height = win_size

            aspect = (pixbuf.get_width() / pixbuf.get_height())

            if aspect < 1:
                height = win_height
                width = aspect * height
                if width > win_width:
                    height = (win_width / width) * height
                    width = win_width
            else:
                width = win_width
                height = (1 / aspect) * width
                if height > win_height:
                    width = (win_height / height) * width
                    height = win_height

            image.set_from_pixbuf(
                pixbuf.scale_simple(
                    width, height, GdkPixbuf.InterpType.BILINEAR))
        else:
            image.clear()
        return False

    def mpd_loop():
        nonlocal pixbuf

        with _mpd_client(mpd_host, mpd_port) as client:
            while True:
                current = client.currentsong()
                if not current:
                        pixbuf = None
                else:
                    try:
                        try:
                            image_bytes = client.readpicture(
                                current['file'])['binary']
                        except:
                            image_bytes = client.albumart(
                                current['file'])['binary']
                        finally:
                            pixbuf = GdkPixbuf.Pixbuf.new_from_stream(
                                Gio.MemoryInputStream.new_from_bytes(
                                    GLib.Bytes.new(image_bytes)
                                ), None)
                    except:
                        pixbuf=None
                GLib.idle_add(set_image)
                client.idle()

    win.show_all()

    def _on_resize(*args):
        if win.get_size() != win_size:
            set_image()

    win.connect('size-allocate', _on_resize)

    thread = threading.Thread(target=mpd_loop)
    thread.daemon = True
    thread.start()


def main():
    parser = configargparse.ArgumentParser(
        default_config_files=['~/.config/mpd-art-box/config'])
    parser.add_argument(
        '-c', '--config', is_config_file=True,
        help='config path')
    parser.add_argument(
        '--host',
        help='MPD host (default: $XDG_RUNTIME_DIR/mpd/socket or localhost)')
    parser.add_argument(
        '--port', type=int, default=6600,
        help='MPD port (default: %(default)s)')
    parser.add_argument('--background-color', default='#000000',
                        metavar='COLOR',
                        help='background-color (default: %(default)s)')
    parser.add_argument('--version', action='version', version=version)
    args = parser.parse_args()

    mpd_host = args.host
    if mpd_host is None:
        runtime_dir = os.environ['XDG_RUNTIME_DIR']
        if runtime_dir:
            socket = pathlib.Path(runtime_dir) / 'mpd' / 'socket'
            if socket.exists():
                mpd_host = str(socket)
    if mpd_host is None:
        mpd_host = 'localhost'

    app_main(mpd_host, args.port, args.background_color)
    Gtk.main()


if __name__ == '__main__':
    main()
