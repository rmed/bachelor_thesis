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

"""Custom widget for agents."""

from gi.repository import Gtk

class WidgetAgentContainer(Gtk.VBox):

    def __init__(self, name):
        super().__init__(spacing=5)

        self.name = Gtk.Label(name)
        self.content = Gtk.HBox(spacing=15)

        self.pack_start(self.name, True, True, 0)
        self.pack_start(Gtk.Separator(), True, True, 0)
        self.pack_start(self.content, True, True, 0)


    def append(self, widget):
        self.content.pack_start(widget, False, False, 0)


class WidgetAgent(Gtk.HBox):

    def __init__(self, name, img):
        super().__init__(spacing=5)

        self.img = Gtk.Image().new_from_file(img)
        self.name = Gtk.Label(name)

        self.pack_start(self.img, True, True, 0)
        self.pack_start(self.name, True, True, 0)

        # self.name = name
        # self.img = img

        # # Setup builder
        # self.builder = Gtk.Builder()
        # self.go = self.builder.get_object

        # self.builder.add_from_file(os.path.join(ui_path, 'widget_agent.glade'))
        # self.content = self.go('container')

        # self.go('label_agent').set_text(name)

        # self = self.content
