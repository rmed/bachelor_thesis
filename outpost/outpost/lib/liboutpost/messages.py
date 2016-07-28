# -*- coding: utf-8 -*-
#
# Outpost for Zoe outpost system
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

"""Message generation code."""

import zoe

def register_agent(host, port, agent):
    """ Register an agent in the central server using the tunnel information.

        host  - host of the central server
        port  - port for the SSH tunnel in central server
        agent - agent name

        Returns a dict with the message
    """
    msg = {
        'dst': 'server',
        'tag': 'register',
        'name': agent,
        'host': host,
        'port': port
    }

    return zoe.MessageBuilder(msg).msg()
