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

"""Main view."""

from blinker import signal
from gi.repository import Gtk
from .widget_agent import WidgetAgent, WidgetAgentContainer
from .settings import Settings
import os

REFRESH_DATA = signal('refresh-data')


class MainWindow(Gtk.ApplicationWindow):

    def __init__(self, app):
        Gtk.Window.__init__(self,
                title='Scout Dashboard',
                application=app,
                window_position=Gtk.WindowPosition.CENTER)

        self.set_default_size(700, 350)
        self.app = self.get_application()

        # Local data
        self.locations = {}
        self.resources = []
        self.logs = [] # Read only 100 at most

        # Refresh flags
        self._started = False
        self.locations_dirty = True
        self.resources_dirty = True
        self.logs_dirty = True

        # Data signals
        def do_refresh(sender, **kwargs):
            """ Blinker does not pass 'self', this is a closure. """
            self._refresh_data(**kwargs)

        self.handle_refresh = do_refresh
        REFRESH_DATA.connect(self.handle_refresh)

        # Setup builder
        self.builder = Gtk.Builder()
        self.go = self.builder.get_object

        # Load UI
        self.builder.add_from_file(
                os.path.join(self.app.ui_path, 'main.glade'))
        self.add(self.go('window_container'))

        self.builder.connect_signals(self)

        # self._reload_notebook(self.go('notebook').get_current_page())

    def on_preferences_activate(self, *args):
        """ Show preferences dialog. """
        dialog = Settings(self)
        dialog.show()

    def on_quit_activate(self, *args):
        """ Quit. """
        self.destroy()

    def on_switch_page(self, *args):
        """ Refresh page. """
        self._reload_notebook(args[2])

    def _reload_notebook(self, current_page=-1):
        """ Reload notebook tab. """
        if current_page == -1:
            current_page = self.go('notebook').get_current_page() or 0

        if current_page == 0:
            # Locations
            self._reload_locations()

        elif current_page == 1:
            # Resources
            self._reload_resources()

        elif current_page == 2:
            # Logs
            self._reload_logs()

    # @REFRESH_DATA.connect
    def _refresh_data(self, **kwargs):
        """ Refresh local data. """
        self.locations = kwargs['locations']
        self.resources = kwargs['resources']
        # self.logs = kwargs['logs']

        self.locations_dirty = True
        self.resources_dirty = True
        self.logs_dirty = True

        if self._started:
            self._reload_notebook()

    def _reload_locations(self):
        if not self.locations_dirty:
            # Nothing to do
            return

        print('reload locations')

        # Delete all widgets
        container = self.go('outposts_container')
        for widget in container.get_children():
            container.remove(widget)

        # Add new widgets
        for key in self.locations:
            new_box = WidgetAgentContainer(key)
            num_agents = len(self.locations[key]) - 1

            for index, location in enumerate(self.locations[key]):
                new_box.append(WidgetAgent(
                    location,
                    os.path.join(self.app.ui_path, 'agent.png')))

                # Separator of agents
                if index < num_agents:
                    new_box.append(Gtk.Separator(
                        orientation=Gtk.Orientation.VERTICAL))

            container.pack_start(new_box, False, False, 5)

        self.show_all()

        self.locations_dirty = False

    def _reload_logs(self):
        if not self.logs_dirty:
            # Nothing to do
            return

        print('reload logs')

        self.logs_dirty = False

    def _reload_resources(self):
        if not self.resources_dirty:
            # Nothing to do
            return

        print('reload resources')

        # Delete all rows
        model = self.go('treeview_resources').get_model()
        model.clear()

        for res in self.resources:
            new_row = [
                res['name'],
                res['location'],
                res['mips'],
                res['timestamp']
            ]

            model.append(new_row)

        self.resources_dirty = False
