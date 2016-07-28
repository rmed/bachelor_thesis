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

"""Logging code."""

import logging


def _level_factory(logger, level):
    """ Factory for creating custom log levels. """
    def custom_level(msg, *args, **kwargs):
        if logger.level >= level:
            return
        logger._log(level, msg, args, kwargs)

    return custom_level

def get_logger(name):
    """ Get a logger with the given name. """
    # Base logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Handler to stdout
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)

    # Formatting
    formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(name)s[%(funcName)s]: %(message)s')

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Custom levels
    # Changes in location and resources
    logging.addLevelName(logging.INFO+1, 'STATUS')
    setattr(logger, 'status', _level_factory(logger, logging.INFO+1))

    return logger
