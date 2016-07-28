# -*- coding: utf-8 -*-
#
# Dashboard for Zoe outpost system
# Copyright (C) 2016  Rafael Medina García <rafamedgar@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Settings view."""

from blinker import signal
from gi.repository import Gtk
import os

SAVE_CONFIG = signal('save-config')

class Settings(Gtk.Window):

    def __init__(self, parent):
        Gtk.Window.__init__(self,
                title='Settings',
                transient_for=parent,
                modal=True,
                destroy_with_parent=True,
                accept_focus=True,
                window_position=Gtk.WindowPosition.CENTER)

        self.parent = parent
        self.app = self.parent.get_application()

        # Setup builder
        self.builder = Gtk.Builder()
        self.go = self.builder.get_object

        # Load UI
        self.builder.add_from_file(
                os.path.join(self.app.ui_path, 'settings.glade'))
        self.add(self.go('window_container'))

        self.builder.connect_signals(self)

        # Update fields
        mode = self.app.config.get('mode', 'local')
        active_mode = 0 if mode == 'local' else 1
        self.go('combobox_mode').set_active(active_mode)

        self.go('entry_zoe_root').set_text(self.app.config.get('zoe_root', ''))
        self.go('entry_zoe_host').set_text(self.app.config.get('zoe_host', ''))
        self.go('entry_zoe_root_remote').set_text(
                self.app.config.get('zoe_root_remote', ''))

    def on_mode_changed(self, *args):
        """ Changed mode of operation. """
        if self.go('combobox_mode').get_active() == 0:
            # Show local
            self.go('local_container').set_visible(True)
            self.go('remote_container').set_visible(False)

        else:
            # Show remote
            self.go('local_container').set_visible(False)
            self.go('remote_container').set_visible(True)

    def on_cancel_clicked(self, *args):
        """ No changes to be made. """
        self.destroy()

    def on_save_clicked(self, *args):
        """ Save changes and notify app. """
        mode = self.go('combobox_mode').get_active()
        conf = {}
        conf['mode'] = 'local' if mode == 0 else 'remote'

        # Local
        conf['zoe_root'] = self.go('entry_zoe_root').get_text()

        # Remote
        conf['zoe_host'] = self.go('entry_zoe_host').get_text()
        conf['zoe_root_remote'] = self.go('entry_zoe_root_remote').get_text()

        # Send signal
        SAVE_CONFIG.send(self, **conf)

        self.destroy()
