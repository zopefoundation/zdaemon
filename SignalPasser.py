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

class SignalPasser:
    def __init__(self, pid):
        self.pid = pid

    def __call__(self, signum, frame):
        import os, sys, signal
        os.kill(self.pid, signum)
        if signum in [signal.SIGTERM, signal.SIGINT]:
            sys.exit(0)

def pass_signals_to_process(pid, signals):
    import signal
    for s in signals:
        signal.signal(s, SignalPasser(pid))
