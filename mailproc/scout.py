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
import email
import re
import sys

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


def do_action(args):
    """ Perform an action with the given parameters. """
    subject = args.subject
    sender = args.sender
    plain_msg = args.plain

    # Check subject
    if subject != 'scout':
        return

    with open(plain_msg, 'r') as f:
        body = f.readline().strip()

    # Check command
    print(body)

    # Help command
    # if body == 'scout help':
    #     for msg in HELP_MSG:
    #         print('feedback %s' % msg)
    #     return

    # Try to find a match for the regular expression
    for key in PATTERNS:
        match = re.findall(key, body)

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
    cmd = cmd + '&dst=scout&sender=%s&src=mail' % sender

    # Send the message
    print(cmd)

def parse_mail():
    """ Parse email message parts. """
    parser = argparse.ArgumentParser()

    parser.add_argument("--msg-sender-uniqueid", action='store', dest='sender')
    parser.add_argument("--mail-subject", action='store', dest='subject')
    parser.add_argument("--plain", action='store')

    args, unknown = parser.parse_known_args()

    do_action(args)


if __name__ == '__main__':
    parse_mail()
