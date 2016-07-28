# -*- coding: utf-8 -*-
#
# Scout for Zoe outpost system
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

"""Global static data."""

import os
from libscout import AgentBook, ZoneBook
from libscout import Balancer

# Base directory for scout files
_BASE_DIR = os.path.join(os.environ['ZOE_HOME'], 'etc', 'scout')

# Databases
AGENT_BOOK = AgentBook(os.path.join(_BASE_DIR, 'agentbook.sqlite'))
ZONE_BOOK = ZoneBook(os.path.join(_BASE_DIR, 'zonebook.sqlite'))

# Config files
SCOUT_CONF = os.path.join(_BASE_DIR, 'scout.conf')
OUTPOST_LIST = os.path.join(_BASE_DIR, 'outpost.list')
ZOE_CONF = os.path.join(os.environ['ZOE_HOME'], 'etc', 'zoe.conf')
ZOE_USERS = os.path.join(os.environ['ZOE_HOME'], 'etc', 'zoe-users.conf')

# Base rules directory
RULES_DIR = os.path.join(_BASE_DIR, 'rules')

# Zoe launcher script
_script_path = os.path.join(os.environ['ZOE_HOME'], 'zoe')
_fallback_script_path = os.path.join(os.environ['ZOE_HOME'], 'zoe.sh')

if os.path.isfile(_script_path):
    ZOE_LAUNCHER = _script_path
else:
    ZOE_LAUNCHER = _fallback_script_path

# Load balancer
BALANCER = Balancer() 
