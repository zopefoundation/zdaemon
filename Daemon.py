##############################################################################
#
# Copyright (c) 2001, 2002 Zope Corporation and Contributors.
# All Rights Reserved.
# 
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
# 
##############################################################################

import os, sys, time, signal, posix

from ZDaemonLogging import pstamp
import Heartbeat
import zLOG

pyth = sys.executable

class KidDiedOnMeError(Exception):
    pass

class ExecError(Exception):
    pass

class ForkError(Exception):
    pass

FORK_ATTEMPTS = 2

def forkit(attempts = FORK_ATTEMPTS):
    while attempts:
        # if at first you don't succeed...
        attempts = attempts - 1
        try:
            pid = os.fork()
        except os.error:
            pstamp('Houston, the fork failed', zLOG.ERROR)
            time.sleep(2)
        else:
            pstamp('Houston, we have forked', zLOG.INFO)
            return pid

def run(argv, pidfile=''):
    if os.environ.has_key('ZDAEMON_MANAGED'):
        # We're the child at this point.
        return
    
    os.environ['ZDAEMON_MANAGED']='TRUE'
    
    if not os.environ.has_key('Z_DEBUG_MODE'):
        # Detach from terminal
        pid = os.fork()
        if pid:
            sys.exit(0)
        posix.setsid()

    while 1:

        try:
            pid = forkit()

            if pid is None:
                raise ForkError

            elif pid:
                # Parent 
                pstamp(('Hi, I just forked off a kid: %s' % pid), zLOG.INFO)
                # here we want the pid of the parent
                if pidfile:
                    pf = open(pidfile, 'w+')
                    pf.write(("%s" % os.getpid()))
                    pf.close()

                while 1: 
                    if not Heartbeat.BEAT_DELAY:
                        p,s = os.waitpid(pid, 0)
                    else:
                        p,s = os.waitpid(pid, os.WNOHANG)
                        if not p:
                            time.sleep(Heartbeat.BEAT_DELAY)
                            Heartbeat.heartbeat()
                            continue
                    if s:
                        pstamp(('Aiieee! %s exited with error code: %s' 
                                % (p, s)), zLOG.ERROR)
                    else:
                        pstamp(('The kid, %s, died on me.' % pid),
                               zLOG.WARNING)
                        raise ForkError

                    raise KidDiedOnMeError

            else:
                # Child
                if __debug__:
                    # non optimized
                    os.execv(pyth, (pyth,) + tuple(argv))
                else:
                    # optimized
                    os.execv(pyth, (pyth, '-O') + tuple(argv))

        except ExecError:
            sys.exit()
        except ForkError:
            sys.exit()
        except KidDiedOnMeError:
            pass
