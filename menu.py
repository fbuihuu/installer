#! /usr/bin/python
# -*- coding: utf-8 -*-
#

class Work(object):

    PHASE_ANYTIME = 0
    PHASE_BEFORE_ROOT = 1
    PHASE_AFTER_ROOT = 2

    def __init__(fn):
        self._callback = fn
        self._rank = rank


class Menu(object):

    STATE_UNCONFIGURED = 0
    STATE_READY = 1
    STATE_PROCESSING = 2
    STATE_FINISHED = 3

    def __init__(self, notify):
        self._state = STATE_UNCONFIGURED
        self._works = []

    def name(self):
        raise NotImplementedError()

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, state):
        # notify listener.
        self._state = state

    def draw(self):
        raise NotImplementedError()


def create_menus():
    for menu in loader.get_modules_in_package(__package__):
        menu.Menu()
