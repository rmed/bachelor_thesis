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

"""Implementation of outpost actions."""

import os
import re
import shutil
import subprocess

from os import environ as env
from os.path import join as path

from . import util
from . import get_logger

# Logging
outlog = get_logger('liboutpost.actions')


def add_agent(conf, agent, port):
    """ Add an agent to the list.

        conf  - ConfigParser instance
        agent - agent name
        port  - port that it will bind to
    """
    section = 'agent ' + agent
    conf.add_section(section)
    conf[section]['port'] = port

def clean_static(path_list):
    """ Remove the given list of static files/directories.

        The list is relative to the root of the outpost files.

        path_list - relative paths to remove
    """
    if not isinstance(path_list, list):
        # Single file to remove
        path_list = [path_list,]

    for p in path_list:
        abs_path = path(env['ZOE_HOME'], p)

        try:
            if os.path.isdir(abs_path):
                # Remove directory tree
                shutil.rmtree(abs_path)

            else:
                # Remove file
                os.remove(abs_path)

        except Exception as e:
            outlog.exception('failed to remove static files')
            pass

def launch_agent(conf, agent):
    """ Launch an agent.

        conf  - ConfigParser instance
        agent - agent name

        Returns boolean indicating result
    """
    outlog.info('launching agent %s' % agent)

    # In outpost?
    if not _is_in_outpost(conf, agent):
        outlog.error('agent %s not in outpost' % agent)
        return False

    # Agent is running?
    if _is_running(agent):
        outlog.error('agent %s is already running' % agent)
        return False

    # Agent exists?
    agent_dir = path(env['ZOE_HOME'], 'agents', agent)
    if not os.path.isdir(agent_dir):
        outlog.error('agent %s does not exist (no files found)' % agent)
        return False

    # Launch agent
    log_file = open(path(env['ZOE_LOGS'], 'outpost.log'), 'a')
    proc = subprocess.Popen([path(env['ZOE_HOME'], 'outpost.sh'),
        'launch-agent', agent], stdout=log_file, stderr=log_file,
        cwd=env['ZOE_HOME'])

    proc.wait()

    return True

def stop_agent(conf, agent):
    """ Stop an agent.

        conf  - ConfigParser instance
        agent - agent name

        Returns boolean indicating result
    """
    outlog.info('stopping agent %s' % agent)

    # In outpost?
    if not _is_in_outpost(conf, agent):
        outlog.error('agent %s not in outpost' % agent)
        return False

    # Agent is running?
    if not _is_running(agent):
        outlog.error('agent %s is not running' % agent)
        return False

    # Stop agent
    log_file = open(path(env['ZOE_LOGS'], 'outpost.log'), 'a')
    proc = subprocess.Popen([path(env['ZOE_HOME'], 'outpost.sh'),
        'stop-agent', agent], stdout=log_file, stderr=log_file,
        cwd=env["ZOE_HOME"])

    proc.wait()

    return True

def gather_info_agents(agents, perf_path):
    """ Gather MIPS information for all agents
        Use pickle so that objects with multiple items can be sent as one.

        agents    - list of agent names
        perf_path - path to the perf executable

        Returns a boolean with status and dict with the information if no error
        occured.
    """
    outlog.info('gathering MIPS')
    procs = []
    info = {}
    SLEEP_TIME = 10 # seconds
    regexp_perf = '^\s*([\d,.]+)\s+instructions\s+.*$'

    # Launch perf process and check output result later
    for agent in agents:
        # Read PID of the agent
        pid_file = path(env['ZOE_VAR'], agent + '.pid')

        if not os.path.isfile(pid_file):
            outlog.error('no PID file found for agent %s' % agent)
            continue

        with open(pid_file, 'r') as f:
            pid = f.read().strip()

        agent_perf = path(env['ZOE_VAR'], agent + '.perf')
        with open(agent_perf, 'w') as lf:
            proc = subprocess.Popen([
                perf_path, 'stat',
                '-e', 'instructions',
                '-p', pid,
                'sleep', str(SLEEP_TIME)], stderr=lf)

        # Store process and wait for it later
        procs.append((proc, agent, agent_perf))

    # Parse outputs
    outlog.info('waiting for perf processes to finish...')
    for p in procs:
        # Wait for process
        outlog.debug('waiting for perf for %s' % p[1])
        p[0].wait()

        # Found instruction count?
        sampled = False

        # Read file
        with open(p[2], 'r') as f:
            lines = f.read().splitlines()

        for line in lines:
            match = re.findall(regexp_perf, line)

            if match:
                # Found the match
                instr = int(match[0].replace(',', '').replace('.', ''))
                outlog.debug('agent %s, instructions: %d' % (p[1], instr))

                mips  = (instr/SLEEP_TIME)/1000000

                # Store info

                info['agent-'+p[1]] = util.serialize(mips)
                outlog.debug('MIPS for agent %s: %f' % (p[1], mips))
                sampled = True
                break

        if not sampled:
            outlog.warning('did not find instruction count of agent %s' % p[1])
            outlog.debug('perf output lines: \n%s' % '\n'.join(lines))

        # Clean output file
        if os.path.isfile(p[2]):
            os.remove(p[2])


    info['dst'] = 'scout'
    info['tag'] = 'agents-gathered'

    return True, info

def refresh_users(users):
    """ Refresh the etc/zoe-users.conf file with the information obtained from
        Central.

        users - serialized string to write to the zoe-users.conf file
    """
    outlog.info('refreshing users list')

    updated = util.deserialize(users)

    with open(path(env['ZOE_HOME'], 'etc', 'zoe-users.conf'), 'w') as f:
        f.write(updated)

def rm_agent(conf, agent):
    """ Remove ang agent from the list and its PID file (if any).

        conf  - ConfigParser instance
        agent - agent name
    """
    outlog.info('removing agent %s' % agent)

    section = 'agent ' + agent
    conf.remove_section(section)

    # Remove agents/ directory
    dir_path = path(env['ZOE_HOME'], 'agents', agent)
    if os.path.isdir(dir_path):
        shutil.rmtree(dir_path)

    # Remove PID file
    pid_file = path(env['ZOE_VAR'], agent + '.pid')
    if os.path.isfile(pid_file):
        os.remove(pid_file)

# Utility functions
def _is_in_outpost(conf, agent):
    """ Check if an agent is in the outpost.

        conf  - ConfigParser instance
        agent - agent name to check

        Returns True or False
    """
    if ('agent ' + agent) in conf.sections():
        return True

    return False

def _is_running(agent):
    """ Check if an agent is running.

        agent - agent name
    """
    # Use .pid files
    pid_path = path(env['ZOE_VAR'], agent + '.pid')

    if os.path.isfile(pid_path):
        return True

    return False
