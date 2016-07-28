# -*- coding: utf-8 -*-
#
# This file is part of Zoe Assistant - https://github.com/guluc3m/gul-zoe
#
# Modified for the Zoe outpost system
#
# Copyright (C) 2013 David Muñoz Díaz <david@gul.es>
# Modifications Copyright (C) 2016 Rafael Medina García <rafamedgar@gmail.com>
#
# This file is distributed under the MIT LICENSE
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import zoe
from zoe.deco import *
from types import MethodType
import base64
import pickle
import threading


# Used to remove bound methods from the automatic attribute parsing
_method_names = ['__travel__', '__prepare__travel__',
        '__settle__', '__settle__outpost__', 'sendbus']

# Serialization padding character
PAD_CHAR = '['


# Private methods to bind to the agent
def __travel__(self):
    """ Automatically store attributes specified in the `_scout_include`
        list, which contains the NAME of the attributes to store in server for
        later restoration.

        Alternatively, it is possible to specify a `_scout_exclude` list to
        include all attributes except the ones specified, or no list at all and
        include all attributes.

        This method may be overriden safely, as the automation is done in
        method `_prepare_travel()`, although it should always return a dict
        with the stored information to send to the server.
    """
    # Store attributes
    extracted = self.__prepare__travel__()

    return extracted

def __settle__(self, info):
    """ Automatically restore all atributes and then await connections
        (resume normal operation).

        This method may be overriden safely, as the automation is done in
        the *private* method `_settle_outpost()`.

        Send a message to the outpost to indicate the agent is ready.

        Parameters:

            info - the information/attributes to restore
    """
    # Restore attributes
    self.__settle__outpost__(info)

def __prepare__travel__(self):
    """ Automatically save agent attributes and return a dict with
        the extracted information.

        If the developer included the `_scout_include` list attribute, that
        will be used to identify the attributes being stored. However, if they
        included the `_scout_exclude` list attribute, the names included there
        will be excluded from the complete list of attributes.

        If no list is provided, all attributes returned by `var()` will be
        used, although the bound methods will be removed.

        Generally, should not be overriden.
    """
    if hasattr(self, '_scout_include'):
        # Inclusion list
        attrs = self._scout_include

    elif hasattr(self, '_scout_exclude'):
        # Exclusion list
        attrs = vars(self).copy()

        # Remove elements
        for a in self._scout_exclude:
            attrs.pop(a, None)

        # Remove bound methods
        for m in _method_names:
            attrs.pop(m, None)

    else:
        # No list, use all attributes
        attrs = vars(self).copy()

        # Remove bound methods
        for m in _method_names:
            attrs.pop(m, None)

    extracted = {}

    # Convert data to bytes
    for key in attrs:
        # extracted[key] = base64.b64encode(
        #         pickle.dumps(getattr(self, key))).decode('utf-8')
        extracted[key] = base64.b64encode(
                pickle.dumps(getattr(self, key))).decode('utf-8') \
                        .replace('=', PAD_CHAR)

    return extracted

def __settle__outpost__(self, info):
    """ Automatically restore agent attributes.

        If the developer included the `_scout_include` list attribute, that
        will be used to identify the attributes being restored.
        However, if they included the `_scout_exclude` list attribute,
        the attributes will be excluded from restoration.

        Otherwise, all the attributes accessible by `vars()` will be used
        (if present).

        Generally, should not be overriden.

        Parameters:

            info - MessageParser instance
    """
    if hasattr(self, '_scout_include'):
        # Inclusion list
        attrs = self._scout_include

    elif hasattr(self, '_scout_exclude'):
        # Exclusion list
        attrs = vars(self).copy()

        # Remove elements
        for a in self._scout_exclude:
            attrs.pop(a, None)

        # Remove bound methods
        for m in _method_names:
            attrs.pop(m, None)

    else:
        # No list, use all attributes
        attrs = vars(self).copy()

        # Remove bound methods
        for m in _method_names:
            attrs.pop(m, None)

    info_map = info._map

    # Convert bytes to data
    for key in attrs:
        if key in info_map:
            # setattr(self, key, pickle.loads(
            #     base64.b64decode(info_map.get(key).encode()))
            # )
            setattr(self, key, pickle.loads(
                base64.b64decode(info_map.get(key).replace(PAD_CHAR, '=') \
                        .encode()))
            )


class OutpostAgent(Agent):
    """ Agent that can be 'moved' across machines. """

    def __call__(self, i):
        """ Overriden """
        instance = i()

        # Append bound methods to the agent
        if not hasattr(instance, '__travel__'):
            setattr(instance, '__travel__', MethodType(__travel__, instance))
        if not hasattr(instance, '__settle__'):
            setattr(instance, '__settle__', MethodType(__settle__, instance))

        # These should not be overriden, but are checked anyway
        if not hasattr(instance, '__prepare__travel__'):
            setattr(instance, '__prepare__travel__',
                MethodType(__prepare__travel__, instance))
        if not hasattr(instance, '__settle__outpost__'):
            setattr(instance, '__settle__outpost__',
                MethodType(__settle__outpost__, instance))

        OutpostDecoratedListener(instance, self._name, self._topic)


class OutpostDecoratedListener(DecoratedListener):
    """ Overriden listener that takes into account special messages used for
        the outpost functionality.
    """

    def __init__(self, agent, name, topic):
        # Flag that indicates whether messages should be parsed or
        # sent to the outpost agent for storage
        self._travelling = False
        self._travel_lock = threading.Lock()

        # Cannot simply use super() because we want the listener to notify
        # the scout right after it has been started (asynchronous)
        #
        # NOTE: CODE BELOW MUST REMAIN EQUAL TO THE ORIGINAL ONE (from voiser)
        #
        # super().__init__(agent, name, topic)
        self._agent = agent
        self._name = name
        self._candidates = []
        self._timed = []
        self._topic = topic
        self._listener = zoe.Listener(self, name = self._name)
        self._agent.sendbus = self._listener.sendbus

        for m in dir(agent):
            k = getattr(agent, m)
            if DEBUG: print("Candidate:", m, "attrs:", k)
            if hasattr(k, "__zoe__tags__"):
                self._candidates.append(k)
            if hasattr(k, "__zoe__anymessage__"):
                self._candidates.append(k)
            if hasattr(k, "__zoe__timed__"):
                self._timed.append(k)
        if DEBUG: print("Candidates:", self._candidates)

        print("Launching timed methods")
        for k in self._timed:
            self._fetchThread = threading.Thread (target = self.timed(k))
            self._fetchThread.start()

        print("Launching agent", self._name)
        # Small code customization

        # if self._listener._dyn:
            # self._listener.start(self.register)
        # else:
            # self._listener.start()

        self._listener.start(self.retrieve_info)

    def receive(self, parser):
        if DEBUG:
            print("Message received:", str(parser))
        tags = parser.tags()

        # Check if message should be executed or deferred
        if "travel!" in tags and not self._travelling:
            # Indicate travel
            with self._travel_lock:
                self._travelling = True

            # Store information
            info = self._agent.__travel__()

            if not info:
                # Nothing to store
                return

            # Add destination and tag
            info['dst'] = 'scout'
            info['tag'] = 'store-info'
            info['agent'] = self._name

            self.sendresponse(zoe.MessageBuilder(info))
            return

        elif "settle!" in tags:
            # Restore information
            self._agent.__settle__(parser)

            # Notify scout
            response = {
                'dst': 'scout',
                'tag': 'retrieve-msg',
                'agent': self._name
            }

            self.sendresponse(zoe.MessageBuilder(response))
            return


        # Travelling?
        if self._travelling:
            orig_map = parser._map.copy()

            # Convert keys
            orig_map["_outpost_dst"] = orig_map["dst"]
            orig_map["dst"] = "scout"

            if orig_map.get("src", None):
                orig_map["_outpost_src"] = orig_map["src"]
                del orig_map["src"]

            if orig_map.get('tag', None):
                orig_map["_outpost_tag"] = orig_map["tag"]

            orig_map["tag"] = ["store-msg", ]

            # Store message for later processing
            self.sendresponse(zoe.MessageBuilder(orig_map))
            return

        self.dispatch(tags, parser)

    def retrieve_info(self, call_register=False):
        """ Send a message to the scout asking for any stored information.

            This method is called automatically when the listener is started
            and registers the agent dynamically when needed.
        """
        # Need to register first?
        if self._listener._dyn:
            self.register()

        retrieval = {
            'dst': 'scout',
            'tag': 'retrieve-info',
            'agent': self._name
        }

        self.sendresponse(zoe.MessageBuilder(retrieval))
