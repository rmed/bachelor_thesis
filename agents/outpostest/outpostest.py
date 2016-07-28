#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Simple agent to test migration capabilities."""

import zoe
from zoe.outpost import *

@OutpostAgent(name="outpostest")
class Outpostest:

    def __init__(self):
        self.a = 0
        self.b = 'test'

        self._scout_include = ['a', 'b']

    @Message(tags=['add'])
    def add(self, parser):
        self.a += 1
        print(self.a)

    @Message(tags=['string'])
    def string(self, parser):
        print(self.b)

    @Message(tags=['echo'])
    def echo(self, parser):
        msg = parser.get('msg')
        print('ECHO: ' + msg)
