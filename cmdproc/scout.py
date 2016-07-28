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

import argparse
import re

# Help message for feedback
HELP_MSG = [' Scout agent commands','---------',
'- scout backup <agent> -> force the creation of the backup directory for a \
given agent (can only be done if agent is in central)',
'- scout close-tunnel <outpost> -> manually close the SSH tunnel to the \
specified outpost',
'- scout hold <agent> -> hold an agent in its current location \
(can only be moved manually)',
'- scout launch-outpost <outpost> -> manually launch a remote outpost',
'- scout locations -> show current agent locations',
'- scout migrate <agent> <outpost> -> migrate an agent to the given outpost',
'- scout open-tunnel <outpost> -> manually open a SSH tunnel to the \
specified outpost',
'- scout retrieve-info <agent> -> force information retrieval for an agent',
'- scout retrieve-msg <agent> -> force message retrieval for an agent',
'- scout status agents -> show current status of the agents',
'- scout status outposts -> show current status of the outposts',
'- scout stop-outpost <outpost> -> manually stop a remote outpost',
'- scout unhold <agent> -> unhold an agent so that it may be moved \
automatically by the scout using the active load balance algorithm'
]

# Base command used for regular expression matching
BASE_CMD = '^scout ([a-z\-]+)(\s?)(.*)$'

# Regular expression commands
PATTERNS = {
    '^scout backup ([a-zA-Z0-9_]+)$': 'message tag=make-backup&agent=$0',

    '^scout close-tunnel ([a-zA-Z0-9_]+)$':
        'message tag=close-tunnel&outpost_id=$0',

    '^scout hold ([a-zA-Z0-9_]+)$': 'message tag=hold-agent&agent=$0',

    '^scout launch-outpost ([a-zA-Z0-9_]+)$':
        'message tag=launch-outpost&outpost_id=$0',

    '^scout locations$': 'message tag=show-locations',

    '^scout migrate ([a-zA-Z0-9_]+) ([a-zA-Z0-9_]+)$':
        'message tag=migrate-agent&agent=$0&outpost_id=$1',

    '^scout open-tunnel ([a-zA-Z0-9_]+)$':
        'message tag=open-tunnel&outpost_id=$0',

    '^scout retrieve-info ([a-zA-Z0-9_]+)$':
        'message tag=retrieve-info&agent=$0',

    '^scout retrieve-msg ([a-zA-Z0-9_]+)$': 'message tag=retrieve-msg&agent=$0',

    '^scout status agents$': 'message tag=show-agent-status',

    '^scout status outposts$': 'message tag=show-outpost-status',

    '^scout stop-outpost ([a-zA-Z0-9_]+)$':
        'message tag=stop-outpost&outpost_id=$0',

    '^scout unhold ([a-zA-Z0-9_]+)$': 'message tag=unhold-agent&agent=$0',
}


def run(args):
    """ Execute the given command.

        This is used to send messages to the scout in order to perform
        specific operations.
    """
    # Help command
    if args.original == 'scout help':
        for msg in HELP_MSG:
            print('feedback %s' % msg)
        return

    # Try to find a match for the regular expression
    for key in PATTERNS:
        match = re.findall(key, args.original)

        if match:
            cmd = PATTERNS.get(key)
            break

    if not match or not cmd:
        return None

    # Get the command arguments
    # Should be a single group
    cmd_args = match[0]

    # Replace arguments in the command
    if type(cmd_args) is tuple:
        # Tuple
        for index, value in enumerate(cmd_args):
            cmd = cmd.replace('$%d' % index, value)

    elif type(cmd_args) is str:
        # Single string
        cmd = cmd.replace('$0', cmd_args)

    # Append additional information to the message
    cmd = cmd + '&dst=scout&sender=%s&src=%s' % (args.sender, args.src)

    # Send the message
    print(cmd)

def get():
    """ Return all the possible regular expression commands to the natural
        language agent.

        As defined in the natural language protocol, regular expressions must
        start and end with a `/` character.
    """
    print('scout help')

    # Must not include newline character (regexp)
    print('/%s/' % BASE_CMD, end='')

def main():
    """ Main function that manages the parsing of arguments.

        get                 - indicates that the script should return
                                available commands
        run                 - indicates that the script should execute some
                                command with the parsed information
        original            - the parsed command
        msg-sender-uniqueid - unique ID of the user (sender)
        msg-src             - where the message came from (src)
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("--get", action='store_true')
    parser.add_argument("--run", action='store_true')
    parser.add_argument("--original", action='store')
    parser.add_argument("--msg-sender-uniqueid", action='store', dest='sender')
    parser.add_argument("--msg-src", action='store', dest='src')

    args, unknown = parser.parse_known_args()

    # Get commands
    if args.get:
        get()

    # Run command
    elif args.run:
        run(args)


if __name__ == '__main__':
    main()
