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

"""Utility functions."""

import base64
import configparser
import os
import paramiko
import pickle
import re
import scp
import shutil
import subprocess
import time

from os import environ as env
from os.path import join as path

from libscout import get_logger
from libscout.static import \
        ZONE_BOOK, SCOUT_CONF, OUTPOST_LIST, RULES_DIR, ZOE_LAUNCHER

# Logging
scoutlog = get_logger('libscout.util')

# Serialization padding character
PAD_CHAR = '['


def close_tunnel(conf, name):
    """ Close the SSH tunnel to a given outpost.

        conf - ConfigParser section with the data of the outpost
        name - name of the outpost
    """
    if not os.path.isfile(path(env['ZOE_VAR'], name + '.pid')):
        # No tunnel currently open?
        scoutlog.error('there is no tunnel open for outpost %s' % name)
        return False

    # Add script logs to scout log
    log_file = open(path(env["ZOE_LOGS"], "scout.log"), "a")

    # Stop the process
    proc = subprocess.Popen([ZOE_LAUNCHER,
        "stop-agent", name], stdout=log_file, stderr=log_file,
        cwd=env["ZOE_HOME"])

    proc.wait()

    scoutlog.info('tunnel to outpost %s should be closed now' % name)
    return True

def copy_dynamic_files(agent, src_base, dst_base, host, username, copy_type):
    """ Copy dynamic agent files to/from a remote machine.

        agent     - agent name
        src_base  - base source directory to concatenate to listed paths
        dst_base  - base destination directory to concatenate to listed paths
        host      - remote host to connect to
        username  - remote username used in the connection
        copy_type - either 'local' when copying FROM remote machine or 'remote'
                    when copying TO remote machine
    """
    scoutlog.info('copying dynamic files of %s' % agent)

    dynamic_path = path(RULES_DIR, agent, 'dynamic')
    if not os.path.isfile(dynamic_path):
        return False

    with open(path(RULES_DIR, agent, 'dynamic'), 'r') as f:
        base_paths = f.read().splitlines()

    path_list = []
    for p in base_paths:
        # Get tuples with remote source and local destination
        path_list.append((path(src_base, p), path(dst_base, p)))

    if copy_type == 'local':
        # Copy to local machine
        remote_get(path_list, host, username)

    elif copy_type == 'remote':
        # Copy to remote machine
        remote_put(path_list, host, username)

def deserialize(data):
    """ Deserialize the given data using base64 encoding and pickle.
        Returns the unpickled object.

        data - data to deserialize (must be in base64 and pickled)
    """
    # return pickle.loads(base64.b64decode(data.encode()))
    return pickle.loads(base64.b64decode(data.replace(PAD_CHAR, '=').encode()))

def gather_info_agents(agents, perf_path):
    """ Gather MIPS information for all agents
        Use pickle so that objects with multiple items can be sent as one.

        agents    - list of agent names
        perf_path - path to the perf executable

        Returns a  dict with the information with agent name as key
        if no error occured.
    """
    scoutlog.info('gathering MIPS')
    procs = []
    info = {}
    SLEEP_TIME = 10 # seconds
    regexp_perf = '^\s*([\d,.]+)\s+instructions\s+.*$'

    # Launch perf process and check output result later
    for agent in agents:
        # Read PID of the agent
        pid_file = path(env['ZOE_VAR'], agent + '.pid')

        if not os.path.isfile(pid_file):
            scoutlog.error('no PID file found for agent %s' % agent)
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
    scoutlog.info('waiting for perf processes to finish...')
    for p in procs:
        # Wait for process
        scoutlog.debug('waiting for perf for %s' % p[1])
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
                scoutlog.debug('agent %s, instructions: %d' % (p[1], instr))

                mips  = (instr/SLEEP_TIME)/1000000

                # Store info
                # Reuse code from remote storage
                info['agent-'+p[1]] = serialize(mips)

                scoutlog.debug('MIPS for agent %s: %f' % (p[1], mips))
                sampled = True
                break

        if not sampled:
            scoutlog.warning('did not find instruction count of agent %s' % p[1])
            scoutlog.debug('perf output lines: \n%s' % '\n'.join(lines))

        # Clean output file
        if os.path.isfile(p[2]):
            os.remove(p[2])

    return info

def get_static_list(agent):
    """ Obtain a list of static files for an agent.

        agent - agent name
    """
    agent_rules = os.path.join(RULES_DIR, agent)

    # Create directory structure from static files
    with open(os.path.join(agent_rules, 'static'), 'r') as f:
        return f.read().splitlines()

def launch_agent(agent):
    """ Launch a local agent.

        agent - agent name
    """
    scoutlog.info('launching agent %s' % agent)

    # Add script logs to scout log
    log_file = open(path(env["ZOE_LOGS"], "scout.log"), "a")

    # Launch agent
    proc = subprocess.Popen([ZOE_LAUNCHER,
        "launch-agent", agent], stdout=log_file, stderr=log_file,
        cwd=env["ZOE_HOME"])

    proc.wait()

def launch_outpost(conf, name):
    """ Launch an outpost.

        If it has already been started, it will be restarted.

        conf - ConfigParser section with the data of the outpost
        name - name of the outpost
    """
    host = conf['host']
    username = conf.get('username')
    directory = conf['directory']

    try:
        # Establish connection
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=username, timeout=10)

        # Launch outpost
        scoutlog.info('launching outpost: %s' % name)
        cmd = 'cd %s; ./outpost.sh restart' % directory

        # Wait for the command to complete (stdin and stderr are not needed)
        _, stdout, _ = ssh.exec_command(cmd)
        stdout.channel.recv_exit_status()

        ssh.close()

    except Exception as e:
        scoutlog.exception('error while launching outpost %s' % name)
        return False

    return True

def mark_hold_agent(agent):
    """ Update the scout config file to mark an agent as held to its current
        machine.

        Returns tuple with boolean and error message (when error occurs).

        agent - name of the agent to hold
    """
    conf = read_config(SCOUT_CONF)

    free_list = conf['agents']['free'].split(' ')
    hold_list = conf['agents']['hold'].split(' ')

    # Previous checks
    if not agent in free_list:
        err_msg = 'agent %s not found in free list' % agent
        scoutlog.error(err_msg)

        return False, err_msg

    if agent in hold_list:
        err_msg = 'agent %s is already in hold list' % agent
        scoutlog.error(err_msg)

        return False, err_msg

    # Add to hold list
    free_list.remove(agent)
    hold_list.append(agent)

    conf['agents']['free'] = ' '.join(free_list)
    conf['agents']['hold'] = ' '.join(hold_list)

    write_config(SCOUT_CONF, conf)
    scoutlog.info('agent %s is now on hold' % agent)

    return True, None

def mark_unhold_agent(agent):
    """ Update the scout config file to mark an agent as free/unheld so that
        it can be moved to other machines.

        agent - name of the agent to hold
    """
    conf = read_config(SCOUT_CONF)

    free_list = conf['agents']['free'].split(' ')
    hold_list = conf['agents']['hold'].split(' ')

    # Previous checks
    if not agent in hold_list:
        err_msg = 'agent %s not found in hold list' % agent
        scoutlog.error(err_msg)

        return False, err_msg

    if agent in free_list:
        err_msg = 'agent %s is already in free list' % agent
        scoutlog.error(err_msg)

        return False, err_msg

    # Add to hold list
    free_list.append(agent)
    hold_list.remove(agent)

    conf['agents']['free'] = ' '.join(free_list)
    conf['agents']['hold'] = ' '.join(hold_list)

    write_config(SCOUT_CONF, conf)
    scoutlog.info('agent %s is now free' % agent)

    return True, None

def open_tunnel(conf, name):
    """ Open the SSH tunnel to communicate with the outpost using autossh.

        The process PID is stored in var/outposts/<name>.pid

        conf - ConfigParser section with the data of the outpost
        name - name of the outpost
    """
    # Create pid file in var/ so that zoe may stop it automatically
    local_tunnel = conf['local_tunnel']
    remote_tunnel = conf['remote_tunnel']
    local_port = os.environ['ZOE_SERVER_PORT']
    remote_port = conf['remote_port']

    if conf.get('username'):
        host = '%s@%s' % (conf['username'], conf['host'])
    else:
        host = conf['host']

    # Open tunnel in background
    scoutlog.info('opening tunnel for outpost: %s' % name)
    cmd = 'autossh -f -N -L %s:localhost:%s -R %s:localhost:%s %s' % (
            local_tunnel, remote_port, remote_tunnel, local_port, host)

    # Save autossh PID file
    pid_file = os.path.join(os.environ['ZOE_VAR'], '%s.pid' % name)
    cmd = 'AUTOSSH_GATETIME=10 AUTOSSH_PIDFILE=%s %s' % (pid_file, cmd)
    # args = shlex.split(cmd)

    # proc = subprocess.Popen(args)
    proc = subprocess.Popen(cmd, shell=True)

    proc.wait()

    # Check exit value
    if proc.returncode != 0:
        # Something happened
        scoutlog.error('could not connect to remote host')

        if os.path.isfile(pid_file):
            os.remove(pid_file)

        return False

    scoutlog.info('tunnel is now open')
    return True

def prepare_backup(agent):
    """ Prepare the directory that is used for central backup and
        for deployment to other machines.

        This directory will only include the relative tree for the static
        files and directories.

        agent      - name of the agent
    """
    scoutlog.info('preparing backup for agent %s' % agent)

    agent_rules = os.path.join(RULES_DIR, agent)

    # Create backup from scratch
    backup_dir = os.path.join(agent_rules, 'backup')

    if os.path.isdir(backup_dir):
        # Remove existing (if any)
        shutil.rmtree(backup_dir)

    os.makedirs(backup_dir, exist_ok=True)

    # Use the static list to determine paths
    static_list = get_static_list(agent)
    src_list = []

    for s_path in static_list:
        orig_path = os.path.join(os.environ['ZOE_HOME'], s_path)

        if os.path.isdir(orig_path):
            # Directory
            for root, dirs, files in os.walk(orig_path):
                for f in files:
                    src_list.append(os.path.join(root, f))

        elif os.path.isfile(orig_path):
            # File
            src_list.append(orig_path)

    # Copy files
    for src in src_list:
        # Directory structure
        dst = src.replace(os.environ['ZOE_HOME'], backup_dir)
        os.makedirs(os.path.dirname(dst), exist_ok=True)

        # Copy file
        shutil.copy(src, dst)

    return True

def read_config(path):
    """ Obtain a ConfigParser instance from the given path. """
    conf = configparser.ConfigParser()
    conf.read(path)

    return conf

def refresh_scout_conf(agent_list):
    """ Refresh the scout configuration file to see if any agents have been
        added or removed manually.

        New agents are added to the 'free' list in `agents` section.

        agent_list  - list of agents found in the rules directory
    """
    scoutlog.info('refreshing scout configuration')

    conf = read_config(SCOUT_CONF)
    ag_sec = conf['agents']

    local_list = agent_list.copy()

    # Check held agents
    hold_list = []

    for a in ag_sec['hold'].split(' '):
        if a in agent_list:
            hold_list.append(a)
            local_list.remove(a)

    # Check free agents
    free_list = []

    for a in ag_sec['free'].split(' '):
        if a in agent_list:
            free_list.append(a)
            local_list.remove(a)

    # New agents are added to the free list
    free_list.extend(local_list)

    conf['agents']['hold'] = ' '.join(hold_list)
    conf['agents']['free'] = ' '.join(free_list)

    write_config(SCOUT_CONF, conf)

def remote_get(paths, outpost_host, username):
    """ Copy given path to local machine.

        This is used to copy dynamic files or directories from the outposts
        when migrating.

        paths        - list of tuples with (src, dst) that indicates the source
                        path in the remote machine and its destination in local
                        one
        outpost_host - Host for connection
        username     - remote username used in the connection
    """
    scoutlog.info('getting remote files from %s' % outpost_host)

    # Open connection for SSH
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(outpost_host, username=username)

    with scp.SCPClient(ssh.get_transport()) as scopy:
        for path_tuple in paths:
            scopy.get(path_tuple[0], path_tuple[1], recursive=True)

    ssh.close()

def remote_put(paths, outpost_host, username):
    """ Copy given path to a remote machine.

        This is used to copy directory contents recursively.

        paths        - list of tuples with (src, dst) that indicates the source
                        path and its destination path in the remote machine
        outpost_host - Host for connection
        username     - remote username used in the connection
    """
    scoutlog.info('uploading local files to %s' % outpost_host)

    # Open connection for SSH
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(outpost_host, username=username)

    with scp.SCPClient(ssh.get_transport()) as scopy:
        for path_tuple in paths:

            if os.path.isdir(path_tuple[0]):
                # Copy directory contents
                for fd in os.listdir(path_tuple[0]):
                    scopy.put(
                        os.path.join(path_tuple[0], fd),
                        path_tuple[1], recursive=True)

            else:
                scopy.put(path_tuple[0], path_tuple[1])

    ssh.close()

def remove_local_files(agent):
    """ Remove local static files taking into account the static rules for the
        given agent.

        agent - name of the agent to remove
    """
    scoutlog.info('removing local files of agent %s' % agent)

    agent_rules = os.path.join(RULES_DIR, agent)

    # Create directory structure from static files
    with open(os.path.join(agent_rules, 'static'), 'r') as f:
        for s_path in f.read().splitlines():
            real_path = os.path.join(os.environ['ZOE_HOME'], s_path)

            if os.path.isdir(real_path):
                # Remove tree
                shutil.rmtree(real_path)

            else:
                # Remove file
                os.remove(real_path)

def restore_backup(agent):
    """ When performing a migration to 'central', the backup files are restored
        to their original location.

        agent - name of the agent to restore
    """
    scoutlog.info('restoring backup of agent %s' % agent)

    backup_dir = os.path.join(RULES_DIR, agent, 'backup')

    if not os.path.isdir(backup_dir):
        scoutlog.error('backup for agent %s does not exist' % agent)
        return False

    # Use the static list to determine paths
    static_list = get_static_list(agent)
    src_list = []

    for s_path in static_list:
        orig_path = os.path.join(backup_dir, s_path)

        if os.path.isdir(orig_path):
            # Directory
            for root, dirs, files in os.walk(orig_path):
                for f in files:
                    src_list.append(os.path.join(root, f))

        elif os.path.isfile(orig_path):
            # File
            src_list.append(orig_path)

    # Copy files/dirs to ZOE_HOME
    for src in src_list:
        # Directory structure
        dst = src.replace(backup_dir, os.environ['ZOE_HOME'])
        os.makedirs(os.path.dirname(dst), exist_ok=True)

        # Copy file
        shutil.move(src, dst)

    return True

def run_local_commands(agent, state):
    """ Run local commands.

        Each command is a different line in file 'etc/scout/rules/agent/<state>'
        and is executed in a shell.

        agent - name of the agent
        state - either 'premig' or 'postmig'
    """
    if state != 'premig' and state != 'postmig':
        scoutlog.error('unknown state "%s"' % state)
        return False

    cmd_file = os.path.join(RULES_DIR, agent, state)

    if not os.path.isfile(cmd_file):
        # Not an error, simply nothing to do
        scoutlog.warning('file for "%s" does not exist' % state)

        return True

    with open(cmd_file, 'r') as f:
        # Execute and wait for each command
        for cmd in f.read().splitlines():
            scoutlog.info('executing: %s' % cmd)

            subprocess.Popen(cmd, shell=True).wait()

def run_remote_commands(agent, state, outpost_conf):
    """ Run remote commands through SSH.

        Each command is a different line in file 'etc/scout/rules/agent/<state>'
        and is executed in a shell with the outpost root as working directory.

        Given that no path is exported, ${ZOE_HOME} is replace manually
        with the outpost root prior to executing the command.

        agent        - name of the agent
        state        - either 'premig' or 'postmig'
        outpost_conf - ConfigParser section for the outpost
    """
    if state != 'premig' and state != 'postmig':
        scoutlog.error('unknown state "%s"' % state)

        return False

    cmd_file = os.path.join(RULES_DIR, agent, state)

    if not os.path.isfile(cmd_file):
        # Not an error, simply nothing to do
        scoutlog.warning('file for "%s" does not exist' % state)

        return True

    host = outpost_conf['host']
    username = outpost_conf.get('username')
    directory = outpost_conf['directory']

    # Open connection for SSH
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username)

    with open(cmd_file, 'r') as f:
        # Execute and wait for each command
        for cmd in f.read().splitlines():
            scoutlog.info('executing: %s' % cmd)

            # Replace ${ZOE_HOME} with outpost Zoe home directory
            cmd = cmd.replace('${ZOE_HOME}', directory)

            _, stdout, _ = ssh.exec_command('cd %s; %s' % (directory, cmd))
            stdout.channel.recv_exit_status()

    ssh.close()

    return True

def serialize(data):
    """ Serialize the given data using pickle and converting it to a base64
        string.

        data - data to serialize (must be picklable)
    """
    # return base64.b64encode(pickle.dumps(data)).decode('utf-8')
    return base64.b64encode(pickle.dumps(data)).decode('utf-8') \
            .replace('=', PAD_CHAR)

def stop_outpost(conf, outpost_id):
    """ Stop an outpost.

        This function does not check if the outpost is currently running or
        not and simply handles the SSH connections and execution of commands.

        conf       - ConfigParser section with the data of the outpost
        outpost_id - name of the outpost to stop
    """
    host = conf['host']
    username = conf.get('username')
    directory = conf['directory']

    try:
        # Establish connection
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=username)

        # Launch outpost
        scoutlog.info('stopping outpost: %s' % outpost_id)
        cmd = 'cd %s; ./outpost.sh stop' % directory

        # Wait for the command to complete (stdin and stderr are not needed)
        _, stdout, _ = ssh.exec_command(cmd)
        stdout.channel.recv_exit_status()

        ssh.close()

    except Exception as e:
        scoutlog.exception('error while stopping outpost %s' % outpost_id)
        return False

    return True

def store_gathered_info_agents(info):
    """ Store the agent's gathered resource information in the zone book.

        info - MIPS of the agents in a dict with `agent-NAME` as key
    """
    for key in filter(
        (lambda a: a.startswith('agent-')), info.keys()):

        # Remove prefix
        agent = key.replace('agent-', '', 1)

        kwargs = {}

        # MIPS
        kwargs['mips'] = deserialize(info[key])

        # Timestamp (stored as float of seconds since epoch)
        kwargs['timestamp'] = time.time()

        if ZONE_BOOK.store_agent_resources(agent, **kwargs):
            scoutlog.info('updated resource information for agent %s' % agent)
            scoutlog.status('resources of agent "%s"; MIPS: %f' % (
                agent, kwargs['mips']))

        else:
            scoutlog.info('failed to update resources for agent %s' % agent)

def write_config(path, conf):
    """ Write the given ConfigParser instance to the specified path. """
    with open(path, 'w') as f:
        conf.write(f)
