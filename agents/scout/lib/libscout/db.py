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

"""Database models."""

import peewee
import time

agent_book_proxy = peewee.Proxy()
zone_book_proxy = peewee.Proxy()


# Agent book
# Stores transient info and messages


class BookModel(peewee.Model):
    class Meta:
        database = agent_book_proxy


class AgentInfo(BookModel):
    """ Used for storing agent information when migrating. """
    agent = peewee.CharField(max_length=128, unique=True, null=False)
    info = peewee.TextField()

    class Meta:
        db_table = 'agent_info'


class AgentMessage(BookModel):
    """ Used for storing delayed agent messages. """
    agent = peewee.CharField(max_length=128, null=False)
    message = peewee.TextField()

    class Meta:
        db_table = 'agent_messages'


# Zone book
# Stores outpost resource information and agent locations

class ZoneModel(peewee.Model):
    class Meta:
        database = zone_book_proxy


class OutpostZone(ZoneModel):
    """ Used for storing outpost name and resource information. """
    name = peewee.CharField(max_length=128, unique=True, null=False)

    # Flags
    is_running = peewee.BooleanField(default=False)

    # Last update
    timestamp = peewee.DateTimeField(default=time.time())

    class Meta:
        db_table = 'outposts'


class AgentZone(ZoneModel):
    name = peewee.CharField(max_length=128, unique=True, null=False)

    # MIPS
    mips = peewee.FloatField(default=0.0)

    # Current location
    location = peewee.ForeignKeyField(OutpostZone, related_name='agents')

    # Last update
    timestamp = peewee.DateTimeField(default=time.time())

    class Meta:
        db_table = 'agents'
