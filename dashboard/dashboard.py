#!/usr/bin/env python3
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

"""Dashboard launcher."""

import os
import shutil
import sys
import threading
import time

try:
    import gi
    gi.require_version('Gtk', '3.0')
except:
    print('Requires version 3.0 of Gtk+')
    sys.exit()

from blinker import signal
from configparser import ConfigParser
from gi.repository import Gtk
from paramiko import SSHClient
from peewee import SqliteDatabase
from playhouse.shortcuts import model_to_dict
from scp import SCPClient

from ui.main import MainWindow
from lib.db import zone_book_proxy, AgentZone

UI_PATH = os.path.join(os.getcwd(), 'glade')
DATA_PATH = os.path.join(os.getcwd(), 'data')
CONF_PATH = os.path.join(os.getcwd(), 'settings.conf')

if not os.path.isdir(DATA_PATH):
    os.mkfifo(DATA_PATH)

REFRESH_DATA = signal('refresh-data')
SAVE_CONFIG = signal('save-config')


class Dashboard(Gtk.Application):

    def __init__(self):
        Gtk.Application.__init__(self)

        self.ui_path = UI_PATH
        self.conf_path = CONF_PATH

        # Data signals
        def do_save_conf(sender, **kwargs):
            """ Blinker does not pass 'self', this is a closure. """
            self._save_conf(**kwargs)

        self.handle_save_conf = do_save_conf
        SAVE_CONFIG.connect(self.handle_save_conf)

        # Read config
        has_conf = False
        self.config = {}

        if os.path.isfile(CONF_PATH):
            parser= ConfigParser()
            parser.read(CONF_PATH)

            self.config = parser['settings']

            has_conf = True

        if not has_conf:
            # Show warning dialog
            dialog = Gtk.MessageDialog(None, 0, Gtk.MessageType.ERROR,
                    Gtk.ButtonsType.OK, 'No configuration file found')
            dialog.run()
            dialog.destroy()

            return

        # Data fetch
        self._data_fetcher = threading.Thread(target=self._fetch_data)
        self._data_fetcher.setDaemon(True)
        self._data_fetcher.start()

        # Wait for a couple of seconds
        time.sleep(2)

        # Database reader
        self.zonebook = SqliteDatabase(
                os.path.join(DATA_PATH, 'zonebook.sqlite'))

        zone_book_proxy.initialize(self.zonebook)

        self._zonebook_parser = threading.Thread(target=self._refresh_zonebook)
        self._zonebook_parser.setDaemon(True)
        self._zonebook_parser.start()

    def do_activate(self):
        window = MainWindow(self)
        window.show()
        window._started = True
        window._reload_notebook()

    def do_startup(self, **kwargs):
        Gtk.Application.do_startup(self)

    def _fetch_data(self):
        """ Fetch data from Zoe instance. """
        while True:
            if self.config['mode'] == 'local':
                # Local mode, copy files
                shutil.copy(
                    os.path.join(self.config['zoe_root'], 'etc', 'scout',
                        'zonebook.sqlite'),
                    DATA_PATH
                )

            elif self.config['mode'] == 'remote':
                # Remote mode, use SCP
                ssh = SSHClient()
                ssh.load_system_host_keys()
                ssh.connect(self.config['zoe_host'])

                # Copy file
                with SCPClient(ssh.get_transport()) as scp:
                    scp.get(os.path.join(self.config['zoe_root_remote'],
                            'etc', 'scout', 'zonebook.sqlite'),
                        os.path.join(DATA_PATH, 'zonebook.sqlite'))

            time.sleep(60)

    def _refresh_zonebook(self):
        """ Refresh information show in interface. """
        while True:
            # Read the database and notify window
            agents = AgentZone.select()

            locations = {}
            info = []

            for agent in agents:
                outpost = agent.location.name

                # Store location
                if outpost not in locations.keys():
                    locations[outpost] = []

                locations[outpost].append(agent.name)

                # Store info
                info.append(model_to_dict(agent, recurse=False))

            REFRESH_DATA.send(self, locations=locations, resources=info)

            time.sleep(30)

    def _save_conf(self, **kwargs):
        """ Save configuration. """
        conf = ConfigParser()
        conf.add_section('settings')

        # Save values
        conf['settings'].update(kwargs)

        with open(CONF_PATH, 'w') as f:
            conf.write(f)

        dialog = Gtk.MessageDialog(None, 0, Gtk.MessageType.INFO,
                Gtk.ButtonsType.OK, 'Restart application to save values')
        dialog.run()
        dialog.destroy()



if __name__ == '__main__':
    app = Dashboard()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)
