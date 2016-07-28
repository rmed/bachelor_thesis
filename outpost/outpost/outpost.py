#!/usr/bin/env python3
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

"""Core server code."""

import asyncore
import socket
import sys
import traceback
import zoe
from os import environ as env
from os.path import join as path

from lib.liboutpost import get_logger
from lib.liboutpost import actions
from lib.liboutpost import messages
from lib.liboutpost import util

# Static information
ZOE_CONF_PATH = path(env['ZOE_HOME'], 'etc', 'zoe.conf')
OUTPOST_CONF_PATH = path(env['ZOE_HOME'], 'etc', 'outpost', 'outpost.conf')

# Logging
outlog = get_logger('outpost')


class Outpost(asyncore.dispatcher):

    def __init__(self):
        """ Initialize the outpost. """
        # Initialize private data
        self._ohost = env['ZOE_SERVER_HOST']
        self._oport = int(env['ZOE_SERVER_PORT'])

        self._main_conf = util.read_config(ZOE_CONF_PATH)
        self._outpost_conf = util.read_config(OUTPOST_CONF_PATH)
        self._id = self._outpost_conf['outpost']['id']
        self._router = {}

        outlog.info('initialized private data')

        # Initialize async server
        asyncore.dispatcher.__init__(self)
        self.create_socket()
        self.set_reuse_addr()
        self.bind((self._ohost, self._oport))
        self.listen(5)

        outlog.info('initialized socket server')

        # Register outpost/self with server
        # This allows the server to dispatch messages directly

        host, port, tunnel = self._get_host_port_tunnel()
        msg = messages.register_agent(host, tunnel, self._id)

        outlog.info('registering outpost with server...')

        self._send(msg, host, port)

        # Register all agents in the server
        for section in filter(
                (lambda a: a.startswith('agent')), self._main_conf.sections()):

            agent = section.replace('agent ', '', 1)

            # Register in server
            msg = messages.register_agent(host, tunnel, agent)
            self._send(msg, host, port)

            outlog.info('registering agent %s with server' % agent)

            # Add to router
            self._router[agent] = int(self._main_conf[section]['port'])

    def handle_accepted(self, sock, addr):
        """ Received a message. Parse some relevant fields and deliver or
            handle the message manually.

            sock - socket connection
            addr - address
        """
        message = ''
        while True:
            data = sock.recv(1024)
            if not data: break
            message = message + data.decode('utf-8')

        sock.close()

        outlog.debug('received: ' + message)

        # Check destination
        parsed = zoe.MessageParser(message, addr=addr)
        dest = parsed.get('dst')

        if not dest:
            outlog.error('message has no destination: %s' % message)
            return

        # Special case: register
        if dest == 'server' and 'register' in parsed.tags():
            outlog.info('received register message for server')

            host, port, tunnel = self._get_host_port_tunnel()

            # Prepare message
            agent = parsed.get('name')
            msg = messages.register_agent(host, tunnel, agent)

            # Save in router
            agent_port = parsed.get('port')
            if agent_port:
                self._router[agent] = int(agent_port)

            return self._send(msg, host, port)

        # For the outpost
        if dest == self._id:
            return self._handle_outpost_msg(parsed)

        # For anyone else
        return self._handle_msg(parsed, dest)

    def handle_error(self):
        """ Skip exceptions (non stop!). """
        traceback.print_exc(sys.stderr)
        pass

    def _get_host_port_tunnel(self):
        """ Return central server host, port and tunnel to which the outpost
            is connected.

            Tunnel is returned as string because it is usually used to compose
            messages, while the port is an integer as it is used for opening
            sockets.
        """
        central = self._outpost_conf['central']

        return central['host'], int(central['port']), central['tunnel']

    def _handle_msg(self, parsed, dest):
        """ Handle delivery of message to agents in outpost or to the central
            server.

            parsed  - MessageParser instance for the message
            dest    - destination of the message
        """
        # First check if agent is in router
        if dest in self._router.keys():
            outlog.info('agent found in router')

            # Send message
            return self._send(parsed._msg, self._ohost, self._router[dest])

        # Not in router check configuration file
        for section in filter(
                (lambda a: a.startswith('agent')), self._main_conf.sections()):

            if dest == section.replace('agent ', '', 1):
                # Agent should be here
                dest_port = int(self._main_conf[section].get('port', '0'))

                if not dest_port:
                    # Unknown...
                    outlog.error('port for agent %s is unknown' % dest)
                    return

                # Update router
                outlog.info('agent found in configuration, updating router')
                self._router[dest] = dest_port

                # Send message
                return self._send(parsed._msg, self._ohost, dest_port)

        # Unknown destination, relay to central server
        outlog.info('unknown destination, relaying to central server')
        host, port, _ = self._get_host_port_tunnel()
        msg = parsed._map

        # Modify replay tag to prevent loops
        current_replay = msg.get('_outpost_replay', 0)

        if current_replay > 5:
            # Discard message
            outlog.info('maximum replay, discarding message: %s' % parsed._msg)
            return

        # Update replay
        msg['_outpost_replay'] = str(current_replay + 1)

        return self._send(zoe.MessageBuilder(msg).msg(), host, port)

    def _handle_outpost_msg(self, parsed):
        """ Message intented for the outpost (perform special operations)

            parsed - MessageParser instance for the message
        """
        action = parsed.get('action')
        if not action:
            outlog.error('no action to perform')
            return


        # Gather agents information:
        if action == 'gather-agents':
            outlog.info('gathering MIPS information for all agents')
            host, port, _ = self._get_host_port_tunnel()

            status, msg = actions.gather_info_agents(
                    self._router.keys(),
                    self._outpost_conf['outpost']['perf_path'])

            if status:
                # Send information
                outlog.info('sending MIPS information for all agents')
                self._send(zoe.MessageBuilder(msg).msg(), host, port)

            else:
                # Show error
                outlog.error('failed to gather information')

            return


        # Update etc/zoe-users.conf file
        if action == 'refresh-users':
            outlog.info('refreshing users list')
            actions.refresh_users(parsed.get('users'))

            return


        # Add agent to list
        if action == 'add-agent':
            agent = parsed.get('agent')
            port = parsed.get('port')

            outlog.info('adding agent %s (port %s) to the list' % (agent, port))

            # Update conf
            actions.add_agent(self._main_conf, agent, port)
            util.write_config(self._main_conf, ZOE_CONF_PATH)

            # Update router
            self._router[agent] = int(port)

            return


        # Remove agent from list
        if action == 'rm-agent':
            agent = parsed.get('agent')

            outlog.info('removing agent %s from list' % agent)

            # Update conf
            actions.rm_agent(self._main_conf, agent)
            util.write_config(self._main_conf, ZOE_CONF_PATH)

            # Update router
            if agent in self._router.keys():
                del self._router[agent]

            outlog.info('removed agent %s from outpost' % agent)

            return


        # Remove the given (agent static) files/directories
        if action == 'clean':
            outlog.info('removing static files')
            actions.clean_static(parsed.get('paths'))

            return


        # Launch agent
        if action == 'launch':
            agent = parsed.get('agent')

            outlog.info('launching agent %s' % agent)

            status = actions.launch_agent(self._main_conf, agent)

            if not status:
                outlog.error('failed to launch agent %s' % agent)
                return

            # Force server register
            host, port, tunnel = self._get_host_port_tunnel()
            msg = messages.register_agent(host, tunnel, agent)
            self._send(msg, host, port)

            outlog.info('launched agent %s' % agent)

            return


        # Stop agent
        if action == 'stop':
            agent = parsed.get('agent')

            outlog.info('stopping agent %s' % agent)

            status, msg = actions.stop_agent(self._main_conf,agent)

            if not status:
                outlog.error('failed to stop agent %s' % agent)
                return

            outlog.info('stopped agent %s' % agent)

            return


        # Reload configuration and router
        if action == 'reload':
            outlog.info('reloading configuration and router')

            self._main_conf = util.read_config(ZOE_CONF_PATH)

            for section in filter(
                    (lambda a: a.startswith('agent')),
                    self._main_conf.sections()):
                name = section.replace('agent ', '', 1)
                port = int(self._main_conf[section]['port'])

                self._router[name] = port

            outlog.info('reloaded configuration and router')

            return


        # Ping message (ignore)
        if action == 'ping':
            outlog.debug('received ping')
            return

    def _send(self, message, host, port):
        """ Send a message to a new socket connection.

            message - message to send (usually relaying)
            host    - host to send to
            port    - port to send to
        """
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            s.sendall(message.encode('utf-8'))

        except Exception as e:
            outlog.exception('failed to send message to %s:%d -> %s' % (
                host, port, message))
            pass

        finally:
            if s:
                s.close()


if __name__ == '__main__':
    # Main loop
    outpost = Outpost()
    asyncore.loop()
