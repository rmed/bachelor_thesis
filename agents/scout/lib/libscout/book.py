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

"""Database managers."""

from .db import agent_book_proxy, zone_book_proxy, \
        AgentInfo, AgentMessage, \
        AgentZone, OutpostZone
from libscout import get_logger
from peewee import SqliteDatabase, IntegrityError
import zoe

# Logging
scoutlog = get_logger('libscout.book')


class AgentBook(object):

    def __init__(self, db):
        """ Initialize the manager for deferred messages and serialized
            information.

            db - absolute path to database file (sqlite)
        """
        self.db = SqliteDatabase(db)
        agent_book_proxy.initialize(self.db)
        self.db.create_tables([AgentInfo, AgentMessage], True)

    def delete_info(self, agent):
        """ Delete stored information for a given agent.

            agent - agent name
        """
        scoutlog.info('deleting stored information of agent %s' % agent)

        try:
            info = AgentInfo.get(AgentInfo.agent == agent)

        except AgentInfo.DoesNotExist:
            scoutlog.error('no information to delete for agent %s' % agent)
            return False

        info.delete_instance()
        return True

    def delete_messages(self, agent):
        """ Delete stored messages for a given agent.

            agent - agent name
        """
        scoutlog.info('deleting stored messages of agent %s' % agent)

        query = AgentMessage.delete().where(AgentMessage.agent == agent)
        query.execute()
        return True

    def get_info(self, agent):
        """ Return the stored information (if any).

            agent - agent name
        """
        scoutlog.info('obtaining stored information of agent %s' % agent)

        try:
            return AgentInfo.get(AgentInfo.agent == agent).info

        except AgentInfo.DoesNotExist:
            scoutlog.error('no information stored for agent %s' % agent)
            return None

    def get_messages(self, agent):
        """ Return all messages for a given agent.

            agent - agent name
        """
        scoutlog.info('obtaining stored stored messages for agent %s' % agent)

        try:
            return [a.message for a in AgentMessage.select().where(
                AgentMessage.agent == agent)]

        except:
            # Not found?
            scoutlog.warning('no messages for agent %s' % agent)
            return []

    def store_info(self, parser):
        """ Store serialized information for a given agent.

            parser - zoe MessageParser instance
        """
        dst = parser.get('agent')
        scoutlog.info('storing information of agent %s' % dst)

        new_map = parser._map.copy()

        # Prepare for direct dispatch
        new_map['dst'] = dst
        del new_map['agent']

        # Original tags removed! (should only have scout ones)
        new_map['tag'] = ['settle!', ]

        # Store message
        raw_msg = zoe.MessageBuilder(new_map).msg()

        try:
            AgentInfo.create(agent=dst, info=raw_msg)

        except IntegrityError as e:
            scoutlog.exception('failed to store information of agent %s' % dst)

    def store_message(self, parser):
        """ Store deferred messages. Convert special tags to their original
            counterparts.

            parser  - zoe MessageParser instance
        """
        dst = parser.get('_outpost_dst')
        src = parser.get('_outpost_src')
        tag = parser.get('_outpost_tag')

        scoutlog.info('storing deferred message for agent %s' % dst)

        new_map = parser._map.copy()

        # Remove unnecessary info
        del new_map['_outpost_dst']
        new_map['dst'] = dst

        if src:
            new_map['src'] = src
            del new_map['_outpost_src']

        if tag:
            new_map['tag'] = tag
            del new_map['_outpost_tag']
        else:
            del new_map['tag']

        # Store message
        raw_msg = zoe.MessageBuilder(new_map, parser._map).msg()
        AgentMessage.create(agent=dst, message=raw_msg)


class ZoneBook(object):

    def __init__(self, db):
        """ Initialize the manager for agent locations and outpost resource
            storage.

            db - absolute path to database file (sqlite)
        """
        self.db = SqliteDatabase(db)
        zone_book_proxy.initialize(self.db)
        self.db.create_tables([OutpostZone, AgentZone], True)

    def get_agents(self):
        """ Return a list of agents.

            Note that this returns the object rather than just the name in
            case other information is wanted.
        """
        return list(AgentZone.select())

    def get_agent_location(self, name):
        """ Get the location for a given agent.

            Returns None if it does not exist.

            name - name of the agent
        """
        scoutlog.info('obtaining location of agent %s' % name)

        try:
            return AgentZone.get(AgentZone.name == name).location.name

        except Exception as e:
            scoutlog.warning('could not get location of agent %s' % name)
            return None

    def get_agents_in(self, outpost_id):
        """ Get the agents found in a given location.

            outpost_id - outpost id to search for
        """
        scoutlog.info('obtaining agents located in %s' % outpost_id)

        try:
            outpost = OutpostZone.get(OutpostZone.name == outpost_id)

        except OutpostZone.DoesNotExist as e:
            scoutlog.warning('outpost %s not found in zone book' % outpost_id)
            return []

        return outpost.agents

    def get_agent_names_in(self, outpost_id):
        """ Get the agent names found in a given location.

            outpost_id - outpost id to search for
        """
        scoutlog.info('obtaining agent names located in %s' % outpost_id)

        try:
            outpost = OutpostZone.get(OutpostZone.name == outpost_id)

        except OutpostZone.DoesNotExist as e:
            scoutlog.warning('outpost %s not found in zone book' % outpost_id)
            return []

        return [agent.name for agent in outpost.agents]

    def get_outposts(self):
        """ Return a list of outposts.

            Note that this returns the object rather than just the name in
            case other information is wanted.
        """
        return list(OutpostZone.select())


    def is_outpost_running(self, name):
        """ Check if an outpost is known to be running or not.

            Returns boolean value.

            name - name of the outpost
        """
        scoutlog.info('checking if outpost %s is currently running' % name)

        try:
            return OutpostZone.get(OutpostZone.name == name).is_running

        except OutpostZone.DoesNotExist as e:
            scoutlog.warning('outpost %s not found in zone book' % name)
            return None

    def move_agent(self, name, location):
        """ Move an agent to the given location.

            name     - name of the agent
            location - new location of the agent
        """
        scoutlog.info('moving agent %s to %s' % (name, location))

        try:
            outpost = OutpostZone.get(OutpostZone.name == location)

            query = AgentZone.update(location=outpost).where(
                    AgentZone.name == name)
            query.execute()
            return True

        except Exception as e:
            scoutlog.exception('could not update location of agent %s' % name)
            return False

    def refresh_agents(self, agent_list):
        """ Refresh the agents table with those in the given list.

            Agents that do not exist will be created, while agents that no
            longer exist will be removed.

            agent_list - list of agent names
        """
        scoutlog.info('refreshing agent list')

        current_list = [agent.name for agent in AgentZone.select()]
        diff_list = list(set(current_list) - set(agent_list))

        # Add new agents
        central, created = OutpostZone.get_or_create(name='central')

        for agent in agent_list:
            new, created = AgentZone.get_or_create(
                name=agent,
                defaults={'location': central})

        # Remove non-existing agents
        if diff_list:
            query = AgentZone.delete().where(AgentZone.name << diff_list)
            query.execute()

    def refresh_outposts(self, outpost_list):
        """ Refresh the outposts table with those in the given list.

            Outposts that do not exist will be created. Outposts that no longer
            exist are kept for historic purposes and to prevent issues with
            keys.

            outpost_list - ConfigParser instance of the outpost list
        """
        scoutlog.info('refreshing outpost list')

        # Add new outposts
        for outpost in filter(
            (lambda o: o.startswith('outpost ')), outpost_list.sections()):

            name = outpost.replace('outpost ', '', 1)
            outpost, created = OutpostZone.get_or_create(name=name)

    def set_outpost_running(self, name, value):
        """ Change the `is_running` flag of an outpost to indicate whether it
            has been started or not.

            name  - name of the outpost to change
            value - boolean indicating whether it is running or not
        """
        scoutlog.info('setting running status of outpost %s to: %r' % (
            name, value))

        try:
            query = OutpostZone.update(is_running=value).where(
                    OutpostZone.name == name)
            query.execute()
            return True

        except Exception as e:
            scoutlog.exception('could not set running status of outpost %s' %
                    name)
            return False

    def store_agent_resources(self, name, **info):
        """ Update the resources for a given agent.

            If no record for an outpost exists, it will be created.

            name - name of the agent
            info - parameters containing the information
        """
        scoutlog.info('updating resources of agent %s' % name)

        # Create agent record if necessary
        agent, created = AgentZone.get_or_create(
            name=name,
            defaults=info)

        if created:
            # Was updated when created
            return True

        # Update information
        try:
            query = AgentZone.update(**info).where(
                    AgentZone.name == name)
            query.execute()
            return True

        except Exception as e:
            scoutlog.exception('error while updating resources of %s' % name)
            return False
