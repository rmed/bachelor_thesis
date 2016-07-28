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

"""Utility functions."""

import base64
import configparser
import pickle

# Serialization padding character
PAD_CHAR = '['


def deserialize(data):
    """ Deserialize the given data using base64 encoding and pickle.
        Returns the unpickled object.

        data - data to deserialize (must be in base64 and pickled)
    """
    # return pickle.loads(base64.b64decode(data.encode()))
    return pickle.loads(base64.b64decode(data.replace(PAD_CHAR, '=').encode()))

def read_config(path):
    """ Read config file specified in path.

        path - path to the file

        Returns new ConfigParser instance.
    """
    conf = configparser.ConfigParser()
    conf.read(path)

    return conf

def serialize(data):
    """ Serialize the given data using pickle and converting it to a base64
        string.

        data - data to serialize (must be picklable)
    """
    # return base64.b64encode(pickle.dumps(data)).decode('utf-8')
    return base64.b64encode(pickle.dumps(data)).decode('utf-8') \
            .replace('=', PAD_CHAR)

def write_config(conf, path):
    """ Writhe the ConfigParser instance to the specified path

        conf - ConfigParser object
        path - path to the file
    """
    with open(path, 'w') as f:
        conf.write(f)
