#! /usr/bin/env python

"""
zdaemon -- run an application as a daemon.

Usage: python zdaemon.py [zdaemon-options] program [program-arguments]

Options:
  -d -- run as a proper daemon; fork a background process, close files etc.
  -h -- print usage message and exit

Arguments:
  program [program-arguments] -- an arbitrary application to run

This daemon manager has two purposes: it restarts the application when
it dies, and (when requested to do so with the -d option) it runs the
application in the background, detached from the foreground tty
session that started it (if any).

Important: if at any point the application exits with exit status 2,
it is not restarted.  Any other form of termination (either being
killed by a signal or exiting with an exit status other than 2) causes
it to be restarted.
"""

"""
XXX TO DO

- A parametrizable "governor" on the automatic restart, limiting the
  frequency of restarts and possible stopping altogether if the
  application fails too often

- A way to stop both the daemon manager and the application.

- A way to restart the application.

- More control over logging (zdaemon logging should be controllable
  separate from application logging).

"""

import os
assert os.name == "posix" # This code makes Unix-specific assumptions
import sys
import getopt
import signal
from stat import ST_MODE

import zLOG

class Daemonizer:

    def __init__(self):
        self.filename = None
        self.args = []
        self.daemon = 0

    def main(self, args=None):
        self.prepare(args)
        self.run()

    def prepare(self, args=None):
        if args is None:
            args = sys.argv[1:]
        self.blather("args=%s" % repr(args))
        try:
            opts, args = getopt.getopt(args, "dh")
        except getopt.error, msg:
            self.usage(str(msg))
        self.parseoptions(opts)
        self.setprogram(args)

    def parseoptions(self, opts):
        self.info("opts=%s" % repr(opts))
        for o, a in opts:
            if o == "-h":
                print __doc__,
                self.exit()
            if o == "-d":
                self.daemon += 1

    def setprogram(self, args):
        if not args:
            self.usage("missing 'program' argument")
        self.filename = self.checkcommand(args[0])
        self.args = args # A list of strings like for execvp()
        self.info("filename=%s; args=%s" %
                  (repr(self.filename), repr(self.args)))

    def checkcommand(self, command):
        if "/" in command:
            filename = command
            try:
                st = os.stat(filename)
            except os.error:
                self.usage("can't stat program %s" % repr(command))
        else:
            path = self.getpath()
            for dir in path:
                filename = os.path.join(dir, command)
                try:
                    st = os.stat(filename)
                except os.error:
                    continue
                mode = st[ST_MODE]
                if mode & 0111:
                    break
            else:
                self.usage("can't find program %s on PATH %s" %
                           (repr(command), path))
        if not os.access(filename, os.X_OK):
            self.usage("no permission to run program %s" % repr(filename))
        return filename

    def getpath(self):
        path = ["/bin", "/usr/bin", "/usr/local/bin"]
        if os.environ.has_key("PATH"):
            p = os.environ["PATH"]
            if p:
                path = p.split(os.pathsep)
        return path

    def run(self):
        self.setsignals()
        if self.daemon:
            self.daemonize()
        self.runforever()

    def setsignals(self):
        signal.signal(signal.SIGTERM, self.sigexit)
        signal.signal(signal.SIGHUP, self.sigexit)
        signal.signal(signal.SIGINT, self.sigexit)

    def sigexit(self, sig, frame):
        self.info("daemon manager killed by signal %s(%d)" %
                  (self.signalname(sig), sig))
        self.exit(1)

    def daemonize(self):
        pid = os.fork()
        if pid != 0:
            # Parent
            self.blather("daemon manager forked; parent exiting")
            self.exit()
        # Child
        self.info("daemonizing the process")
        os.close(0)
        sys.stdin = sys.__stdin__ = open("/dev/null")
        os.close(1)
        sys.stdout = sys.__stdout__ = open("/dev/null", "w")
        os.close(2)
        sys.stderr = sys.__stderr__ = open("/dev/null", "w")
        os.setsid()

    def runforever(self):
        self.info("daemon manager started")
        while 1:
            self.forkandexec()

    def forkandexec(self):
        pid = os.fork()
        if pid != 0:
            # Parent
            self.info("forked child pid %d" % pid)
            wpid, wsts = os.waitpid(pid, 0)
            self.reportstatus(wpid, wsts)
        else:
            # Child
            self.startprogram()

    def startprogram(self):
        try:
            self.blather("about to exec %s" % self.filename)
            try:
                os.execv(self.filename, self.args)
            except os.error, err:
                self.panic("can't exec %s: %s" %
                           (repr(self.filename), str(err)))
        finally:
            os._exit(127)

    def reportstatus(self, pid, sts):
        if os.WIFEXITED(sts):
            es = os.WEXITSTATUS(sts)
            msg = "pid %d: exit status %s" % (pid, es)
            if es == 0:
                self.info(msg)
            else:
                self.warning(msg)
                if es == 2:
                    self.exit(es)
        elif os.WIFSIGNALED(sts):
            signum = os.WTERMSIG(sts)
            signame = self.signalname(signum)
            msg = ("pid %d: terminated by signal %s(%s)" %
                   (pid, signame, signum))
            if hasattr(os, "WCOREDUMP"):
                iscore = os.WCOREDUMP(sts)
            else:
                iscore = s & 0x80
            if iscore:
                msg += " (core dumped)"
            self.warning(msg)
        else:
            # XXX what should we do here?
            signum = os.WSTOPSIG(sts)
            signame = self.signalname(signum)
            msg = "pid %d: stopped by signal %s(%s)" % (pid, signame, signum)
            self.warning(msg)

    signames = None

    def signalname(self, sig):
        """Return the symbolic name for signal sig.

        Returns 'unknown' if there is no SIG name bound to sig in the
        signal module.
        """

        if self.signames is None:
            self.setupsignames()
        return self.signames.get(sig, "unknown")

    def setupsignames(self):
            self.signames = {}
            for k, v in signal.__dict__.items():
                startswith = getattr(k, "startswith", None)
                if startswith is None:
                    continue
                if startswith("SIG") and not startswith("SIG_"):
                    self.signames[v] = k

    # Error handling

    def usage(self, msg):
        self.errwrite("Error: %s\n" % str(msg))
        self.error(str(msg))
        self.errwrite("For help, use zdaemon.py -h\n")
        self.exit(2)

    def errwrite(self, msg):
        sys.stderr.write(msg)

    def exit(self, sts=0):
        sys.exit(sts)

    # Log messages with various severities

    def trace(self, msg):
        self.log(msg, zLOG.TRACE)

    def debug(self, msg):
        self.log(msg, zLOG.DEBUG)

    def blather(self, msg):
        self.log(msg, zLOG.BLATHER)

    def info(self, msg):
        self.log(msg, zLOG.INFO)

    def warning(self, msg):
        self.log(msg, zLOG.WARNING)

    def error(self, msg):
        self.log(msg, zLOG.ERROR)

    def panic(self, msg):
        self.log(msg, zLOG.PANIC)

    def getsubsystem(self):
        return "ZD:%d" % os.getpid()

    def log(self, msg, severity=zLOG.INFO):
        zLOG.LOG(self.getsubsystem(), severity, msg)

def main(args=None):
    d = Daemonizer()
    d.main(args)

if __name__ == "__main__":
    main()
