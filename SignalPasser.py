##############################################################################
#
# Copyright (c) 2001 Zope Corporation and Contributors. All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################

""" A module used for passing signals to children """

import os, sys, signal

class SignalPasser:
    def __init__(self, pid):
        self.pid = pid

    def __call__(self, signum, frame):
        # send the signal to our child
        os.kill(self.pid, signum)
        # we want to die ourselves if we're signaled with SIGTERM or SIGINT
        if signum in [signal.SIGTERM, signal.SIGINT]:
            sys.exit(0)
