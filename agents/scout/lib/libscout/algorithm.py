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

"""Load balancing algorithms."""

from libscout import get_logger

# Logging
scoutlog = get_logger('libscout.algorithm')


class Balancer(object):
    """ Class that contains load balancing algorithms.

        All the functions must return a map with the format:

        result = {
            outpost_id: [name of agents that should be here]
        }
    """

    def __init__(self):
        """ Initialize the map that contains the relations name-algorithm. """
        self._algorithms = {
            'equal': self._equal_load,
            'prio': self._user_prio
        }

    def get_algorithm(self, name):
        """ Get the algorithm to execute from the map given the name.

            This is the only method that should be accessed directly.

            name - unique name of the algorithm to use
        """
        return self._algorithms.get(name, None)

    def _equal_load(self, outmap):
        """ Maintains an equal load among all outposts.

            This requires the MIPS a machine is capable of and current MIPS
            obtained from the agents.

            outmap - map of outposts and agents they contain
        """
        total_mips = {}
        current_load = []
        agentsmap = {}

        result = {}

        # Parse the necessary information
        for outpost in outmap.keys():
            result[outpost] = []

            current_load.append((outpost, 0))
            total_mips[outpost] = float(outmap[outpost]['mips'])
            agentsmap.update(outmap[outpost]['agents'])

            # Update current load values
            # for agent in outmap[outpost]['agents']:
            #     ag_load = float(agentsmap[agent]['mips'] / total_mips[outpost])

            #     for index, load in enumerate(current_load):
            #         if load[0] == outpost:
            #             load[1] = load[1] + ag_load
            #             current_load[index] = load
            #             break

        # Balance the load
        for agent in agentsmap.keys():
            location = agentsmap[agent]['location']
            mips = agentsmap[agent]['mips']
            is_free = agentsmap[agent]['is_free']

            ag_load = float(mips / total_mips[location])

            # Can be moved?
            if not is_free:
                for index, load in enumerate(current_load):
                    if load[0] == location:
                        scoutlog.info('agent "%s" on hold in outpost "%s"' % (
                            agent, location))

                        outpost_load = load[1] + ag_load

                        current_load[index] = (location, outpost_load)
                        scoutlog.debug('new load of outpost %s: %f' % (
                            location, outpost_load))
                        break
                continue

            # Remove load from its current machine
            # for index, load in enumerate(current_load):
            #     if load[0] == location:
            #         load[1] = load[1] - ag_load
            #         current_load[index] = load
            #         break

            # Order machine loads
            current_load.sort(key=lambda tup: tup[1])

            # Add to first outpost
            new_location = current_load[0][0]
            new_ag_load = float(mips / total_mips[new_location])
            outpost_load = current_load[0][1] + new_ag_load

            current_load[0] = (new_location, outpost_load)
            scoutlog.debug('new load of outpost %s: %f' % (
                new_location, outpost_load))

            # Add to result
            scoutlog.info('agent "%s" will be moved to outpost "%s"' % (
                agent, new_location))
            result[new_location].append(agent)

        return result

    def _user_prio(self, outmap):
        """ Assign agents to outposts based on user priority.

            This balancer will try to fill an outpost up to its 80% available
            MIPS using information gathered and the 'priority' configuration.

            outmap - map of outposts and agents they contain
        """
        total_mips = {}
        current_load = {}
        agentsmap = {}
        priorities = []

        result = {}

        # Parse the necessary information
        for outpost in outmap.keys():
            result[outpost] = []

            # Save priority
            priorities.append((outpost, outmap[outpost]['priority']))

            current_load[outpost] = 0
            total_mips[outpost] = float(outmap[outpost]['mips'])
            agentsmap.update(outmap[outpost]['agents'])

            # Update current load values
            # for agent in outmap[outpost]['agents']:
            #     ag_load = float(agentsmap[agent]['mips'] / total_mips[outpost])

            #     current_load[outpost] = current_load[outpost] + ag_load

        # Order machine priorities
        priorities.sort(key=lambda tup: tup[1])

        # Balance the load
        for agent in agentsmap.keys():
            location = agentsmap[agent]['location']
            mips = agentsmap[agent]['mips']
            is_free = agentsmap[agent]['is_free']

            ag_load = float(mips / total_mips[location])

            # Can be moved?
            if not is_free:
                current_load[location] = current_load[location] + ag_load
                continue

            # Remove load from current machine
            # current_load[location] = current_load[location] - ag_load

            # Add to outpost with highest priority (lowest value)
            # Check that it does not exceed 80%

            chosen = False
            for prio in priorities:
                # Check new hypothetical load
                outpost = prio[0]
                ag_load = float(mips / total_mips[outpost])

                hypo_load = ag_load + current_load[outpost]

                if hypo_load < 0.8:
                    scoutlog.info('agent "%s" will be moved to outpost "%s"' % (
                        agent, outpost))

                    result[outpost].append(agent)
                    current_load[outpost] = hypo_load

                    scoutlog.debug('new load of outpost %s: %f' % (
                        outpost, hypo_load))

                    chosen = True
                    break

            # Force migration to central
            if not chosen:
                scoutlog.info('forcing migration of "%s" to central' % agent)

                ag_load = float(mips / total_mips['central'])
                current_load['central'] = current_load['central'] + ag_load

                result['central'].append(agent)

                scoutlog.debug('new load of outpost %s: %f' % (
                    'central', ag_load))


        scoutlog.debug('Balancer result: ' + str(result))

        return result
