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

"""Message generation code."""

import datetime
import os
import zoe
from libscout.static import \
        ZONE_BOOK, SCOUT_CONF, ZOE_CONF, OUTPOST_LIST, RULES_DIR, ZOE_LAUNCHER
from libscout.util import read_config

def add_agent(outpost_id, agent):
    """ Add an agent to the remote outpost list.

        outpost_id - unique id of the outpost
        agent      - agent name
    """
    # Get port
    main_conf = read_config(ZOE_CONF)
    port = main_conf['agent '+ agent]['port']

    add = {
        'dst': outpost_id,
        'action': 'add-agent',
        'agent': agent,
        'port': port
    }

    return zoe.MessageBuilder(add).msg()

def clean_static(outpost_id, path_list):
    """ Tell the outpost to remove the given list of paths.

        These files are usually agent static files that have to be removed when
        migration occurs.

        outpost_id - unique id of the outpost
        path_list  - absolute paths to the files or directories to remove
    """
    remove = {
        'dst': outpost_id,
        'paths': path_list,
        'action': 'clean'
    }

    return zoe.MessageBuilder(remove).msg()

def feedback_agent_locations(outpost_list):
    """ Build feedback message with agent locations.

        outpost_list - ConfigParser instance from outpost list
    """
    msg = '# Agent locations\n\n'

    # Get list of outposts (+ central)
    outposts = [s for s in outpost_list.sections() if s.startswith('outpost ')]
    outposts.append('central')

    for s in outposts:

        # Mind the blank space
        outpost = s.replace('outpost ', '', 1)

        # Get agents in this outpost
        msg += '%s\n' % outpost
        msg += '---------\n'

        o_agents = ZONE_BOOK.get_agent_names_in(outpost)

        for agent in o_agents:
            msg += '%s\n' % agent

        msg += '\n'

    return msg

def feedback_agent_status(agent_list):
    """ Build feedback message with agent status.

        agent_list - list of known outpost agents (database objects)
    """
    # Read scout config for status
    conf = read_config(SCOUT_CONF)

    msg = '# Agent status\n\n'

    for agent in agent_list:
        msg += '%s\n' % agent.name
        msg += '---------\n'
        msg += 'ON HOLD\n' if agent.name in conf['agents']['hold'] else 'FREE\n'
        msg += '- Location: %s\n' % agent.location.name
        msg += '- MIPS: %f\n' % agent.mips
        msg += '- Last update: %s\n\n' % datetime.datetime.fromtimestamp(
                agent.timestamp).strftime('%d-%m-%Y %H:%M:%S')

    msg += '\n'

    return msg

def feedback_outpost_status(outpost_list):
    """ Build feedback message with outpost status.

        outposts_list - list of known outposts
    """
    # Read outpost config for details
    scout_conf = read_config(SCOUT_CONF)
    out_conf = read_config(OUTPOST_LIST)

    msg = '# Outpost status\n\n'

    for outpost in outpost_list:
        if outpost.name == 'central':
            msg += '%s\n' % outpost.name
            msg += '---------\n'
            msg += 'ONLINE\n' # If this is working, then it is online
            msg += '- Balancer: %s\n' % scout_conf['general'].get(
                    'balance','N/A')
            msg += '- MIPS: %f\n' % scout_conf['general'].getfloat('mips', -1)
            msg += '- Priority: %d\n' % scout_conf['general'].getint(
                    'priority', -1)
            msg += '- Last update: %s\n\n' % datetime.datetime.fromtimestamp(
                    outpost.timestamp).strftime('%d-%m-%Y %H:%M:%S')

            continue

        if 'outpost ' + outpost.name not in out_conf.sections():
            continue

        conf = out_conf['outpost ' + outpost.name]

        msg += '%s\n' % outpost.name
        msg += '---------\n'
        msg += 'ONLINE\n' if outpost.is_running else 'OFFLINE\n'
        msg += '- Host: %s\n' % conf['host']
        msg += '- Remote port: %d\n' % conf.getint('remote_port')
        msg += '- Local tunnel: %d\n' % conf.getint('local_tunnel')
        msg += '- Remote tunnel: %d\n' % conf.getint('remote_tunnel')
        msg += '- Remote directory: %s\n' % conf['directory']
        msg += '- MIPS: %f\n' % conf.getfloat('mips', -1)
        msg += '- Priority: %d\n' % conf.getint('priority', -1)
        msg += '- Last update: %s\n\n' % datetime.datetime.fromtimestamp(
                outpost.timestamp).strftime('%d-%m-%Y %H:%M:%S')

    msg += '\n'

    return msg

def feedback_permissions():
    """ Build feedback message used when user does not have the
        required permissions (admin level).
    """
    return 'You do not have the required permissions'

def launch_agent(outpost_id, agent):
    """ Tell the outpost to launch an agent.

        outpost_id - unique id of the outpost
        agent - agent name
    """
    launch = {
        'dst': outpost_id,
        'agent': agent,
        'action': 'launch'
    }

    return zoe.MessageBuilder(launch).msg()

def moving_agent(agent):
    """ Create message telling agent that it is being moved. """
    moving = {
        'dst': agent,
        'tag': 'travel!'
    }

    return zoe.MessageBuilder(moving).msg()

def register_local(agent):
    """ Register a local agent with the server. """
    # Get port
    main_conf = read_config(ZOE_CONF)
    port = main_conf['agent '+ agent]['port']

    register = {
        'dst': 'server',
        'name': agent,
        'host': os.environ['ZOE_SERVER_HOST'],
        'port': port,
        'tag': 'register'
    }

    return zoe.MessageBuilder(register).msg()

def refresh_users(outpost_id, users):
    """ Send an up-to-date version of the etc/zoe-users.conf config file
        to the specified outpost.

        outpost_id - unique id of the outpost
        users      - serialized ConfigParser instance for the users config file
    """
    refresh_users = {
        'dst': outpost_id,
        'users': users,
        'action': 'refresh-users'
    }

    return zoe.MessageBuilder(refresh_users).msg()

def rm_agent(outpost_id, agent):
    """ Remove an agent from the outpost list.

        outpost_id - unique id of the outpost
        agent      - agent name
    """
    remove = {
        'dst': outpost_id,
        'action': 'rm-agent',
        'agent': agent
    }

    return zoe.MessageBuilder(remove).msg()

def terminate_agent(agent):
    """ Create message telling agent to terminate. """
    terminate = {
        'dst': agent,
        'tag': 'exit!'
    }

    return zoe.MessageBuilder(terminate).msg()

def outpost_gather_agents(outpost_id):
    """ Create a message asking an outpost for information on its agents'
        resources.
    """
    gather = {
        'dst': outpost_id,
        'action': 'gather-agents'
    }

    return zoe.MessageBuilder(gather).msg()
