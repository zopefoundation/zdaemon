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

import os, sys, signal
import zLOG

pyth = sys.executable

class DieNow(Exception):
    pass

class SignalPasser:
    """ A class used for passing signal that the daemon receives along to
    its child """
    def __init__(self, pid):
        self.pid = pid

    def __call__(self, signum, frame):
        # send the signal to our child
        os.kill(self.pid, signum)
        # we want to die ourselves if we're signaled with SIGTERM or SIGINT
        if signum in [signal.SIGTERM, signal.SIGINT]:
            raise DieNow

PASSED_SIGNALS = (
    signal.SIGHUP,
    signal.SIGINT,
    signal.SIGQUIT,
    signal.SIGUSR1,
    signal.SIGUSR2,
    signal.SIGTERM,
    )

def run(argv, pidfile=''):
    if os.environ.has_key('ZDAEMON_MANAGED'):
        # We're being run by the child.
        return

    os.environ['ZDAEMON_MANAGED']='TRUE'

    if not os.environ.has_key('Z_DEBUG_MODE'):
        detach() # detach from the controlling terminal

    while 1:
        try:
            pid = os.fork()
            if pid:
                # We're the parent (the daemon process)
                # pass all "normal" signals along to our child, but don't
                # respond to them ourselves unless they say "die"!
                for sig in PASSED_SIGNALS:
                    signal.signal(sig, SignalPasser(pid))
                pstamp('Started subprocess: pid %s' % pid, zLOG.INFO)
                write_pidfile(pidfile)
                p, s = wait(pid) # waitpid will block until child exit
                log_pid(p, s)
                if s:
                    # continue and restart because our child died
                    # with a nonzero exit code, meaning he bit it in
                    # an unsavory way (likely a segfault or something)
                    continue
                else:
                    pstamp("zdaemon exiting", zLOG.INFO)
                    # no need to restart, our child wanted to die.
                    raise DieNow

            else:
                # we're the child (Zope/ZEO)
                args = [pyth]
                if not __debug__:
                    # we're running in optimized mode
                    args.append('-O')
                os.execv(pyth, tuple(args) + tuple(argv))

        except DieNow:
            sys.exit()

def detach():
    # do the funky chicken dance to detach from the terminal
    pid = os.fork()
    if pid: sys.exit(0)
    os.close(0); sys.stdin  = open('/dev/null')
    os.close(1); sys.stdout = open('/dev/null','w')
    os.close(2); sys.stderr = open('/dev/null','w')
    os.setsid()

def write_pidfile(pidfile):
    if pidfile:
        pf = open(pidfile, 'w+')
        pf.write(("%s\n" % os.getpid()))
        pf.close()

def wait(pid):
    while 1:
        try:
            p,s = os.waitpid(pid, 0)
        except OSError:
            # catch EINTR, it's raised as a result of
            # interrupting waitpid with a signal
            # and we don't care about it.
            continue
        else:
            return p, s

def log_pid(p, s):
    if os.WIFEXITED(s):
        es = os.WEXITSTATUS(s)
        msg = "terminated normally, exit status: %s" % es
    elif os.WIFSIGNALED(s):
        signum = os.WTERMSIG(s)
        signame = get_signal_name(signum)
        msg = "terminated by signal %s(%s)" % (signame, signum)
        if hasattr(os, 'WCOREDUMP'):
            iscore = os.WCOREDUMP(s)
        else:
            iscore = s & 0x80
        if iscore:
            msg += " (core dumped)"
    else:
        # XXX what should we do here?
        signum = os.WSTOPSIG(s)
        signame = get_signal_name(signum)
        msg = "stopped by signal %s(%s)" % (signame, signum)
    pstamp('Process %s %s' % (p, msg), zLOG.ERROR)

_signals = None

def get_signal_name(n):
    """Return the symbolic name for signal n.

    Returns 'unknown' if there is no SIG name bound to n in the signal
    module.
    """
    global _signals
    if _signals is None:
        _signals = {}
        for k, v in signal.__dict__.items():
            startswith = getattr(k, 'startswith', None)
            if startswith is None:
                continue
            if startswith('SIG') and not startswith('SIG_'):
                _signals[v] = k
    return _signals.get(n, 'unknown')

def pstamp(message, sev):
    zLOG.LOG("zdaemon", sev, message)
