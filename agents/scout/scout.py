#!/usr/bin/env python3
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

"""Core code of the agent."""

import sys
sys.path.append('./lib')

import os
import threading
import time
import zoe
from zoe.deco import Agent, Message, Timed
from zoe.models.users import Users

# Helpful namespaces
from libscout import get_logger
from libscout import messages as scoutmsg
from libscout import static as scoutatic
from libscout import util as scoutil


# Locks
LOCK_AGENT_BOOK = threading.Lock()
LOCK_ZONE_BOOK = threading.Lock()
LOCK_SCOUT_CONF = threading.Lock()
LOCK_OUTPOST_LIST = threading.Lock()
LOCK_MIGRATION = threading.Lock()

# Logging
scoutlog = get_logger('scout')


@Agent(name='scout')
class Scout:

    def __init__(self):
        self._starting = True
        # Refresh the configurations and zone book
        self.refresh_info()

        # Open the tunnels
        # scoutil.open_tunnels()

        # Launch the outposts
        # scoutil.launch_outposts()

        # Open tunnels and launch outposts
        outpost_list = scoutil.read_config(scoutatic.OUTPOST_LIST)
        for outpost in filter(
                (lambda o: o.startswith('outpost ')), outpost_list.sections()):

            name = outpost.replace('outpost ', '', 1)
            scoutlog.info('opening tunnel and launching %s' % name)

            # Open tunnel
            if not scoutil.open_tunnel(outpost_list[outpost], name):
                scoutlog.error('failed to open tunnel to outpost %s' % name)

                # Set as 'not running'
                scoutatic.ZONE_BOOK.set_outpost_running(name, False)
                continue

            # Launch outpost
            if not scoutil.launch_outpost(outpost_list[outpost], name):
                scoutlog.error('failed to launch outpost %s' % name)

                # Set as 'not running'
                scoutatic.ZONE_BOOK.set_outpost_running(name, False)
                continue

            # Set as running
            scoutatic.ZONE_BOOK.set_outpost_running(name, True)

    @Timed(600)
    def balance_agents(self):
        """ Periodic method that determines best location for the agents given
            available outposts information and moves them around.
        """
        # Skip first iteration
        if self._starting:
            self._starting = False
            return

        scoutlog.info('starting agent balancing')

        with LOCK_OUTPOST_LIST:
            outposts = scoutil.read_config(scoutatic.OUTPOST_LIST)

        with LOCK_SCOUT_CONF:
            conf = scoutil.read_config(scoutatic.SCOUT_CONF)

        outpost_map = {}

        with LOCK_MIGRATION:
            # Get algorithm to use
            alg_name = conf['general'].get('balance', None)
            if not alg_name:
                scoutlog.info('load balancing not enabled')
                return

            algorithm = scoutatic.BALANCER.get_algorithm(alg_name)
            if not algorithm:
                scoutlog.error('unknown algorithm "%s"' % alg_name)
                return

            scoutlog.info('using algorithm: "%s"' % alg_name)

            # Get current locations and information of outposts
            for s in filter(
                (lambda o: o.startswith('outpost ')), outposts.sections()):

                # Mind the blank space
                outpost = s.replace('outpost ', '', 1)

                # Check if running
                if not scoutatic.ZONE_BOOK.is_outpost_running(outpost):
                    err_msg = 'outpost %s is not running'
                    scoutlog.warning(err_msg)
                    continue

                agents = scoutatic.ZONE_BOOK.get_agents_in(outpost)

                # Store agents and config information in outpost map
                outpost_map[outpost] = {'agents': {}}

                for key in outposts[s]:
                    outpost_map[outpost][key] = outposts[s][key]

                for agent in agents:
                    # Can the agent be moved?
                    if agent.name in conf['agents']['free']:
                        is_free = True
                    else:
                        is_free = False

                    outpost_map[outpost]['agents'][agent.name] = {
                        'location': outpost,
                        'mips': agent.mips,
                        'timestamp': agent.timestamp,
                        'is_free': is_free
                    }

            # Information on Central
            agents = scoutatic.ZONE_BOOK.get_agents_in('central')

            # Store agents and config information in outpost map
            outpost_map['central'] = {'agents': {}}

            for key in conf['general']:
                outpost_map['central'][key] = conf['general'][key]

            for agent in agents:
                # Can the agent be moved?
                if agent.name in conf['agents']['free']:
                    is_free = True
                else:
                    is_free = False

                outpost_map['central']['agents'][agent.name] = {
                    'location': 'central',
                    'mips': agent.mips,
                    'timestamp': agent.timestamp,
                    'is_free': is_free
                }

            # Execute the balancing algorithm and check new locations
            scoutlog.info('executing balancing algorithm')
            balanced_map = algorithm(outpost_map.copy())

            scoutlog.debug('balance result: ' + str(balanced_map))

            # Compare locations to see what agents must be moved
            migrations = []

            for outpost in balanced_map.keys():
                scoutlog.info('checking migrations to outpost "%s"' % outpost)

                new_agents = balanced_map[outpost]
                current_agents = outpost_map[outpost]['agents'].keys()

                incoming = list(set(new_agents) - set(current_agents))

                for inc in incoming:
                    scoutlog.debug('registering migration of "%s" to %s' % (
                        inc, outpost))

                    migrations.append({
                        'outpost_id': outpost,
                        'agent': inc
                    })

        # Run migrations
        scoutlog.info('starting agent migrations...')

        for mig in migrations:
            self.migrate_agent(mig)

    @Timed(180)
    def gather_agent_info(self):
        """ Periodic method that obtains MIPS for each agent.

            If the agent is not in central, a message will be sent to the
            relevant outpost.
        """
        # First send to all the outposts
        with LOCK_OUTPOST_LIST:
            conf = scoutil.read_config(scoutatic.OUTPOST_LIST)

        scoutlog.info('sending agent gathering messages')

        # Build messages to send
        for s in filter(
            (lambda o: o.startswith('outpost ')), conf.sections()):

            # Mind the blank space
            outpost = s.replace('outpost ', '', 1)

            # Check if running
            with LOCK_ZONE_BOOK:
                if not scoutatic.ZONE_BOOK.is_outpost_running(outpost):
                    err_msg = 'outpost %s is not running'
                    scoutlog.warning(err_msg)
                    continue

            # Deliver message
            self.sendbus(scoutmsg.outpost_gather_agents(outpost))

        scoutlog.info('gathering agents in central')

        # Gather info for all agents in central
        scout_conf = scoutil.read_config(scoutatic.SCOUT_CONF)
        sys_perf = scout_conf['general']['perf_path']

        with LOCK_ZONE_BOOK:
            agent_list = scoutatic.ZONE_BOOK.get_agent_names_in('central')

        gathered = scoutil.gather_info_agents(agent_list, sys_perf)
        scoutil.store_gathered_info_agents(gathered)

    @Timed(60)
    def refresh_info(self):
        """ Periodic method that refreshes scout config file and zone book
            to see if agents or outposts have been added.
        """
        agent_list = os.listdir(scoutatic.RULES_DIR)

        scoutlog.info('refreshing scout configuration')

        # Check scout conf
        with LOCK_SCOUT_CONF:
            scoutil.refresh_scout_conf(agent_list)

        with LOCK_OUTPOST_LIST:
            outpost_list = scoutil.read_config(scoutatic.OUTPOST_LIST)

        scoutlog.info('refreshing zone book information')

        # Check zone book
        with LOCK_ZONE_BOOK:
            scoutatic.ZONE_BOOK.refresh_agents(agent_list)
            scoutatic.ZONE_BOOK.refresh_outposts(outpost_list)

    @Timed(60)
    def refresh_users(self):
        """ Periodic method that reads the etc/zoe-users.conf file and sends
            the serialized ConfigParser instance to all the outposts.
        """
        scoutlog.info('sending updated users list to outposts')

        # Obtain the latest version of the config file
        with open(scoutatic.ZOE_USERS, 'r') as f:
            users = scoutil.serialize(f.read())

        # Send to all the outposts
        with LOCK_OUTPOST_LIST:
            outposts = scoutil.read_config(scoutatic.OUTPOST_LIST)

        # Build messages to send
        for s in filter(
            (lambda o: o.startswith('outpost ')), outposts.sections()):

            # Mind the blank space
            outpost = s.replace('outpost ', '', 1)

            # Check if running
            with LOCK_ZONE_BOOK:
                if not scoutatic.ZONE_BOOK.is_outpost_running(outpost):
                    err_msg = 'outpost %s is not running'
                    scoutlog.warning(err_msg)
                    continue

            # Deliver message
            self.sendbus(scoutmsg.refresh_users(outpost, users))

    @Message(tags=['close-tunnel'])
    def close_tunnel(self, parser):
        """ Manually close an SSH tunnel.

            Relevant parser keys:
                outpost_id - ID of the outpost to stop
                sender     - unique ID of the user that sent the message
                src        - where the message came from (zoe agent)
        """
        if not self._has_permissions(parser.get('sender'), parser.get('src')):
            return None

        outpost_id = parser.get('outpost_id')

        scoutlog.info('closing tunnel to outpost %s' % outpost_id)

        # Check if outpost is known
        with LOCK_OUTPOST_LIST:
            outposts = scoutil.read_config(scoutatic.OUTPOST_LIST)

            if 'outpost ' + outpost_id not in outposts.sections():
                err_msg = 'unknown outpost: %s' % outpost_id
                scoutlog.error(err_msg)

                return self._feedback(err_msg, parser=parser)

        # Check if there is a tunnel open
        if not os.path.isfile(
                os.path.join(os.environ['ZOE_VAR'], outpost_id + '.pid')):

            err_msg = 'there is no tunnel to outpost %s' % outpost_id
            scoutlog.error(err_msg)

            return self._feedback(err_msg, parser=parser)

        # Close the tunnel
        with LOCK_MIGRATION:
            if not scoutil.close_tunnel(
                    outposts['outpost ' + outpost_id], outpost_id):

                err_msg = 'failed to close tunnel to outpost %s' % outpost_id
                scoutlog.error(err_msg)

                return self._feedback(err_msg, parser=parser)

        msg = 'closed tunnel to outpost %s' % outpost_id
        scoutlog.info(msg)

        scoutlog.status('tunnel to outpost "%s" is now closed' % outpost_id)

        return self._feedback(msg, parser=parser)

    @Message(tags=['hold-agent'])
    def hold_agent(self, parser):
        """ Hold an agent in a given outpost (or central server). This way, the
            agent will not be taken into account when performing moves.

            Relevant parser keys:

                agent  - agent name
                sender - unique ID of the user that sent the message (if any)
                src    - where the message came from (zoe agent)
        """
        if not self._has_permissions(parser.get('sender'), parser.get('src')):
            return None

        agent = parser.get('agent')

        if not agent:
            err_msg = 'no agent name provided'
            scoutlog.error(err_msg)

            return self._feedback(err_msg, parser=parser)

        with LOCK_SCOUT_CONF:
            status, err_msg = scoutil.mark_hold_agent(agent)

        # Check status
        if status:
            msg = 'agent %s is now on hold' % agent
            scoutlog.info(msg)

            return self._feedback(msg, parser=parser)

        msg = 'error holding agent %s: %s' % (agent, err_msg)
        scoutlog.error(msg)

        return self._feedback(msg, parser=parser)

    @Message(tags=['launch-outpost'])
    def launch_outpost(self, parser):
        """ Manually launch an outpost. This does not open the SSH
            tunnel.

            Updates the zone book to indicate that the outpost is running.

            Relevant parser keys:
                outpost_id - ID of the outpost to launch
                sender     - unique ID of the user that sent the message
                src        - where the message came from (zoe agent)
        """
        if not self._has_permissions(parser.get('sender'), parser.get('src')):
            return None

        outpost_id = parser.get('outpost_id')

        scoutlog.info('launching outpost %s' % outpost_id)

        # Check if outpost is known
        with LOCK_OUTPOST_LIST:
            outposts = scoutil.read_config(scoutatic.OUTPOST_LIST)

            if 'outpost ' + outpost_id not in outposts.sections():
                err_msg = 'unknown outpost: %s' % outpost_id
                scoutlog.error(err_msg)

                return self._feedback(err_msg, parser=parser)

        # Check if it is supposed to be stopped and mark as running
        with LOCK_ZONE_BOOK:
            if scoutatic.ZONE_BOOK.is_outpost_running(outpost_id):
                err_msg = 'outpost %s is already running' % outpost_id
                scoutlog.error(err_msg)

                return self._feedback(err_msg, parser=parser)

            if not scoutatic.ZONE_BOOK.set_outpost_running(outpost_id, True):
                err_msg = 'failed to change running status of %s' % outpost_id
                scoutlog.error(err_msg)

                return self._feedback(err_msg, parser=parser)

        # Launch the outpost
        with LOCK_MIGRATION:
            if not scoutil.launch_outpost(outposts['outpost ' + outpost_id],
                    outpost_id):

                err_msg = 'failed to remotely launch outpost %s' % outpost_id
                scoutlog.error(err_msg)

                # Rollback
                scoutatic.ZONE_BOOK.set_outpost_running(outpost_id, False)

                return self._feedback(err_msg, parser=parser)

        msg = 'launched outpost %s' % outpost_id
        scoutlog.info(msg)

        scoutlog.status('outpost "%s" is now running' % outpost_id)

        return self._feedback(msg, parser=parser)

    @Message(tags=['make-backup'])
    def make_backup(self, parser):
        """ Create the backup file tree for a given agent.

            This can only be done if the agent is in the central server.

            Relevant parser keys:

                agent  - agent name
                sender - unique ID of the user that sent the message (if any)
                src    - where the message came from (zoe agent)
        """
        if not self._has_permissions(parser.get('sender'), parser.get('src')):
            return None

        agent = parser.get('agent')

        if not agent:
            err_msg = 'no agent name provided'
            scoutlog.error(err_msg)

            return self._feedback(err_msg, parser=parser)

        # Check if the agent is in central
        with LOCK_OUTPOST_LIST:
            if scoutatic.ZONE_BOOK.get_agent_location(agent) != 'central':
                err_msg = 'agent %s is not in central' % agent
                scoutlog.error(err_msg)

                return self._feedback(err_msg, parser=parser)

        # Create backup
        scoutil.prepare_backup(agent)

        msg = 'created backup for agent %s' % agent
        scoutlog.info(msg)

        return self._feedback(msg, parser=parser)

    @Message(tags=['migrate-agent'])
    def migrate_agent(self, parser):
        """ Send an agent to the specified outpost (or central).

            Relevant parser keys:
                outpost_id - destination (outpost id or central)
                agent      - agent name
                sender     - unique ID of the user that sent the message (if any)
                src        - where the message came from (zoe agent)
        """
        if not self._has_permissions(parser.get('sender'), parser.get('src')):
            return None

        agent = parser.get('agent')
        outpost_id = parser.get('outpost_id')

        # Check if agent is registered for moving
        with LOCK_SCOUT_CONF:
            sconf = scoutil.read_config(scoutatic.SCOUT_CONF)

            hold = sconf['agents']['hold'].split(' ')
            free = sconf['agents']['free'].split(' ')

            if agent not in hold and agent not in free:
                err_msg = 'agent %s cannot migrate' % agent
                scoutlog.error(err_msg)

                return self._feedback(err_msg, parser=parser)

        # Read outpost list and check destination
        with LOCK_OUTPOST_LIST:
            outposts = scoutil.read_config(scoutatic.OUTPOST_LIST)

            if 'outpost ' + outpost_id not in outposts.sections() and (
                    outpost_id != 'central'):
                err_msg = 'unknown outpost: %s' % outpost_id
                scoutlog.error(err_msg)

                return self._feedback(err_msg, parser=parser)

        # Get current location and status of the new outpost
        with LOCK_ZONE_BOOK:
            current_location = scoutatic.ZONE_BOOK.get_agent_location(agent)

            if not current_location:
                # Where is the agent?
                err_msg = 'agent %s cannot be located' % agent
                scoutlog.error(err_msg)

                return self._feedback(err_msg, parser=parser)

            is_running = scoutatic.ZONE_BOOK.is_outpost_running(outpost_id)

        # Cannot migrate to a closed outpost
        if outpost_id != 'central' and not is_running:
            err_msg = 'outpost %s is not running/accessible' % outpost_id
            scoutlog.error(err_msg)

            return self._feedback(err_msg, parser=parser)

        # Do not try to move an agent to its current location
        if current_location == outpost_id:
            err_msg = 'agent is already in %s' % outpost_id
            scoutlog.warning(err_msg)

            return self._feedback(err_msg, parser=parser)

        # Notify agent that it is being moved
        scoutlog.info('notifying %s of the migration' % agent)
        self.sendbus(scoutmsg.moving_agent(agent))

        # Give some time to terminate current operations
        time.sleep(10)

        # Tell agent to terminate
        scoutlog.info('terminating agent %s' % agent)
        self.sendbus(scoutmsg.terminate_agent(agent))

        with LOCK_MIGRATION:
            # Check origin
            if current_location == 'central':
                # Create backup dir for deployment
                scoutil.prepare_backup(agent)

                # Remove local files
                scoutil.remove_local_files(agent)

            else:
                # Remove static files
                file_list = scoutil.get_static_list(agent)
                self.sendbus(
                        scoutmsg.clean_static(current_location, file_list))

                # Copy dynamic files to central
                outpost_item = outposts['outpost ' + current_location]
                scoutil.copy_dynamic_files(agent, outpost_item['directory'],
                        os.environ['ZOE_HOME'], outpost_item['host'],
                        outpost_item.get('username'), 'local')

                # Remove from remote outpost
                self.sendbus(scoutmsg.rm_agent(current_location, agent))


            # Check destination
            if outpost_id != 'central':
                # Moving to external outpost
                outpost_item = outposts['outpost ' + outpost_id]

                # Execute pre-migration commands (SSH)
                scoutil.run_remote_commands(agent, 'premig', outpost_item)

                # Copy files using SCP
                backup_dir = os.path.join(scoutatic.RULES_DIR, agent, 'backup')
                scoutil.remote_put(
                        [(backup_dir, outpost_item['directory']),],
                        outpost_item['host'], outpost_item.get('username'))

                # Copy dynamic files
                scoutil.copy_dynamic_files(
                        agent, os.environ['ZOE_HOME'],
                        outpost_item['directory'], outpost_item['host'],
                        outpost_item.get('username'), 'remote')

                # Execute post-migration commands (SSH)
                scoutil.run_remote_commands(agent, 'postmig', outpost_item)

                # Add agent to remote list
                self.sendbus(scoutmsg.add_agent(outpost_id, agent))

                # Give some time to outpost
                time.sleep(5)

                # Launch agent
                self.sendbus(scoutmsg.launch_agent(outpost_id, agent))

            else:
                # Moving to central

                # Execute pre-migration commands
                scoutil.run_local_commands(agent, 'premig')

                # Move the backup to ZOE_HOME
                scoutil.restore_backup(agent)

                # Execute post-migration commands
                scoutil.run_local_commands(agent, 'postmig')

                # Force local register
                self.sendbus(scoutmsg.register_local(agent))

                # Launch agent
                scoutil.launch_agent(agent)

            # Check for error
            if not scoutatic.ZONE_BOOK.move_agent(agent, outpost_id):
                err_msg = 'failed to move agent %s' % agent
                scoutlog.error(err_msg)

                return self._feedback(err_msg, parser=parser)

            # Update list
            msg = 'agent %s moved to %s' % (agent, outpost_id)
            scoutlog.info(msg)

            scoutlog.status('new location of agent "%s": %s' % (
                agent, outpost_id))

            return self._feedback(msg, parser=parser)

    @Message(tags=['open-tunnel'])
    def open_tunnel(self, parser):
        """ Manually open a tunnel to the specified outpost.

            Relevant parser keys:
                outpost_id - ID of the outpost to stop
                sender     - unique ID of the user that sent the message
                src        - where the message came from (zoe agent)
        """
        if not self._has_permissions(parser.get('sender'), parser.get('src')):
            return None

        outpost_id = parser.get('outpost_id')

        scoutlog.info('opening tunnel to outpost %s' % outpost_id)

        # Check if outpost is known
        with LOCK_OUTPOST_LIST:
            outposts = scoutil.read_config(scoutatic.OUTPOST_LIST)

            if 'outpost ' + outpost_id not in outposts.sections():
                err_msg = 'unknown outpost: %s' % outpost_id
                scoutlog.error(err_msg)

                return self._feedback(err_msg, parser=parser)

        # Check if there is a tunnel open
        if os.path.isfile(
                os.path.join(os.environ['ZOE_VAR'], outpost_id + '.pid')):

            err_msg = 'there is already a tunnel to outpost %s' % outpost_id
            scoutlog.error(err_msg)

            return self._feedback(err_msg, parser=parser)

        # Open the tunnel
        with LOCK_MIGRATION:
            if not scoutil.open_tunnel(
                    outposts['outpost ' + outpost_id], outpost_id):

                err_msg = 'failed to open tunnel to outpost %s'
                scoutlog.error(err_msg)

                return self._feedback(err_msg, parser=parser)

        msg = 'opened tunnel to outpost %s' % outpost_id
        scoutlog.info(msg)

        scoutlog.status('tunnel to outpost "%s" is now open' % outpost_id)

        return self._feedback(msg, parser=parser)

    @Message(tags=['retrieve-info'])
    def retrieve_info(self, parser):
        """ Retrieve agent information and send it back.

            Relevant parser keys:
                agent  - name of the agent to restore
                sender - unique ID of the user that sent the message (if any)
                src    - where the message came from (zoe agent)
        """
        if not self._has_permissions(parser.get('sender'), parser.get('src')):
            return None

        agent = parser.get('agent')

        if not agent:
            err_msg = 'no agent name provided'
            scoutlog.error(err_msg)

            return self._feed(err_msg, parser=parser)

        scoutlog.info('retrieving info for %s' % agent)

        with LOCK_AGENT_BOOK:
            info = scoutatic.AGENT_BOOK.get_info(agent)

            if info:
                # Dispatch info
                self.sendbus(zoe.MessageBuilder.fromparser(
                    zoe.MessageParser(info)).msg())

                scoutatic.AGENT_BOOK.delete_info(agent)

                return self._feedback('retrieved stored information',
                        parser=parser)

        scoutlog.info('no information stored for agent %s' % agent)
        self._feedback('no information stored, will retrieve messages anyway',
                parser=parser)

        # Retrieve stored messages anyway
        return self.retrieve_messages(parser)

    @Message(tags=['retrieve-msg'])
    def retrieve_messages(self, parser):
        """ Retrieve all stored messages for the settled agent.

            Relevant parser keys:
                agent  - name of the agent to restore
                sender - unique ID of the user that sent the message (if any)
                src    - where the message came from (zoe agent)
        """
        if not self._has_permissions(parser.get('sender'), parser.get('src')):
            return None

        agent = parser.get('agent')

        if not agent:
            err_msg = 'no agent name provided'
            scoutlog.error(err_msg)

            return self._feedback(err_msg, parser=parser)

        scoutlog.info('retrieving messages for %s' % agent)

        # Suppose that agent is settled
        with LOCK_AGENT_BOOK:
            # Get messages
            msg_list = scoutatic.AGENT_BOOK.get_messages(agent)

        # Dispatch past messages
        for msg in msg_list:
            self.sendbus(zoe.MessageBuilder.fromparser(
                zoe.MessageParser(msg)).msg())

        # Delete stored messages
        with LOCK_AGENT_BOOK:
            scoutatic.AGENT_BOOK.delete_messages(agent)

        msg = 'retrieved stored messages for agent %s' % agent
        scoutlog.info(msg)

        return self._feedback(msg, parser=parser)

    @Message(tags=['show-locations'])
    def show_agent_locations(self, parser):
        """ Show a list of agents sorted by outpost in which they are located.

            Relevant parser keys:
                sender - unique ID of the user that sent the message
                src    - where the message came from (zoe agent)
        """
        if not self._has_permissions(parser.get('sender'), parser.get('src')):
            return None

        scoutlog.info('obtaining agent locations')

        with LOCK_OUTPOST_LIST:
            conf = scoutil.read_config(scoutatic.OUTPOST_LIST)

        with LOCK_ZONE_BOOK:
            msg = scoutmsg.feedback_agent_locations(conf)

        return self._feedback(msg, parser=parser)

    @Message(tags=['show-agent-status'])
    def show_agent_status(self, parser):
        """ Show the status of all the agents.

            This includes whether they are on hold or free.

            Relevant parser keys:
                sender - unique ID of the user that sent the message
                src    - where the message came from (zoe agent)
        """
        if not self._has_permissions(parser.get('sender'), parser.get('src')):
            return None

        scoutlog.info('obtaining status of agents')

        with LOCK_ZONE_BOOK:
            agents = scoutatic.ZONE_BOOK.get_agents()

        with LOCK_SCOUT_CONF:
            msg = scoutmsg.feedback_agent_status(agents)

        return self._feedback(msg, parser=parser)

    @Message(tags=['show-outpost-status'])
    def show_outpost_status(self, parser):
        """ Show the status of all the outposts.

            Relevant parser keys:
                sender - unique ID of the user that sent the message
                src    - where the message came from (zoe agent)
        """
        if not self._has_permissions(parser.get('sender'), parser.get('src')):
            return None

        scoutlog.info('obtaining status of outposts')

        with LOCK_ZONE_BOOK:
            outposts = scoutatic.ZONE_BOOK.get_outposts()

        with LOCK_SCOUT_CONF:
            msg = scoutmsg.feedback_outpost_status(outposts)

        return self._feedback(msg, parser=parser)

    @Message(tags=['stop-outpost'])
    def stop_outpost(self, parser):
        """ Manually force an outpost to stop. This does not close the SSH
            tunnel.

            Updates the zone book to indicate that the outpost is not running.

            Relevant parser keys:
                outpost_id - ID of the outpost to stop
                sender     - unique ID of the user that sent the message
                src        - where the message came from (zoe agent)
        """
        if not self._has_permissions(parser.get('sender'), parser.get('src')):
            return None

        outpost_id = parser.get('outpost_id')

        scoutlog.info('stopping outpost %s' % outpost_id)

        # Check if outpost is known
        with LOCK_OUTPOST_LIST:
            outposts = scoutil.read_config(scoutatic.OUTPOST_LIST)

            if 'outpost ' + outpost_id not in outposts.sections():
                err_msg = 'unknown outpost: %s' % outpost_id
                scoutlog.error(err_msg)

                return self._feedback(err_msg, parser=parser)

        # Check if it is supposed to be running and mark as stopped
        with LOCK_ZONE_BOOK:
            if not scoutatic.ZONE_BOOK.is_outpost_running(outpost_id):
                err_msg = 'outpost %s is not currently running' % outpost_id
                scoutlog.error(err_msg)

                return self._feedback(err_msg, parser=parser)

            if not scoutatic.ZONE_BOOK.set_outpost_running(outpost_id, False):
                err_msg = 'failed to change running status of %s' % outpost_id
                scoutlog.error(err_msg)

                return self._feedback(err_msg, parser=parser)

        # Stop the outpost
        with LOCK_MIGRATION:
            if not scoutil.stop_outpost(outposts['outpost ' + outpost_id],
                    outpost_id):

                err_msg = 'failed to remotely stop outpost %s' % outpost_id
                scoutlog.error(err_msg)

                # Rollback
                scoutatic.ZONE_BOOK.set_outpost_running(outpost_id, True)

                return self._feedback(err_msg, parser=parser)

        msg = 'stopped outpost %s' % outpost_id
        scoutlog.info(msg)

        scoutlog.status('outpost "%s" is now stopped' % outpost_id)

        return self._feedback(msg, parser=parser)

    @Message(tags=['store-info'])
    def store_agent_info(self, parser):
        """ Stores the agent's information for later use.

            The message is transformed so that when retrieved, it can be
            sent directly.

            Relevant parser keys:
                agent - name of the agent
        """
        scoutlog.info('storing information of agent %s' % parser.get('agent'))

        with LOCK_AGENT_BOOK:
            scoutatic.AGENT_BOOK.store_info(parser)

    @Message(tags=['agents-gathered'])
    def store_agent_res(self, parser):
        """ Stores the agent's used resources on the machine it is located.

            Relevant parser keys:
                agent-NAME - MIPS of the agent specified in the key
        """
        scoutlog.info('received message to update agent resources')

        with LOCK_ZONE_BOOK:
            scoutil.store_gathered_info_agents(parser._map)

    @Message(tags=['store-msg'])
    def store_message(self, parser):
        """ Stores deferred message to send to the settled agent when ready.

            The message is transformed so that when retrieved, it can be
            sent directly.

            Relevant parser keys:
                _outpost_dst - original destination (agent name)
                _outpost_src - original sender of the message
                _outpost_tag - original tags
        """
        scoutlog.info('storing deffered message for agent %s' %
                parser.get('_outpost_dst'))

        with LOCK_AGENT_BOOK:
            scoutatic.AGENT_BOOK.store_message(parser)

    @Message(tags=['unhold-agent'])
    def unhold_agent(self, parser):
        """ Free an agent so that it can be moved to other machines or outposts.

            Relevant parser arguments:

                agent - agent name
                sender - unique ID of the user that sent the message (if any)
                src    - where the message came from (zoe agent)
        """
        if not self._has_permissions(parser.get('sender'), parser.get('src')):
            return None

        agent = parser.get('agent')

        if not agent:
            err_msg = 'no agent name provided'
            scoutlog.error(err_msg)

            return self._feedback(err_msg, parser=parser)

        with LOCK_SCOUT_CONF:
            status, err_msg = scoutil.mark_unhold_agent(agent)

        # Check status
        if status:
            msg = 'agent %s is now free' % agent
            scoutlog.info(msg)

            return self._feedback(msg, parser=parser)

        msg = 'error unholding agent %s: %s' % (agent, err_msg)
        scoutlog.error(msg)

        return self._feedback(msg, parser=parser)

    def _has_permissions(self, user, src=None):
        """ Check if the user has permissions necessary to interact with the
            scout (belongs to group 'admins')
        """
        # No user, manual commands from terminal
        if not user or user in Users().membersof('admins'):
            return True

        # Does not have permission, send message
        self._feedback(scoutmsg.feedback_permissions(), user, src)
        return False

    def _feedback(self, message, user=None, dst=None, parser=None):
        """ Send feedback message to the given user.

            message - message to send
            user    - user to send the message to
            dst     - where to send the message to (zoe agent)
            parser  - MessageParser instance from which to get user and dst
                        if these are not provided
        """
        # Get from parser?
        if parser:
            user = parser.get('sender')
            dst = parser.get('src')

        if not user and not dst:
            # No information provided
            return

        to_send = {
            'dst': 'relay',
            'relayto': dst,
            'to': user
        }

        if dst == 'mail':
            to_send['subject'] = 'Scout'
            to_send['txt'] = message
        else:
            to_send['msg'] = message

        self.sendbus(zoe.MessageBuilder(to_send).msg())
