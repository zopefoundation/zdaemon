#!python
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
"""zrdun -- run an application as a daemon.

Usage: python zrdun.py [zrdun-options] program [program-arguments]

Options:
-C/--configuration URL -- configuration file or URL
-b/--backoff-limit SECONDS -- set backoff limit to SECONDS (default 10)
-d/--daemon -- run as a proper daemon; fork a subprocess, setsid(), etc.
-f/--forever -- run forever (by default, exit when backoff limit is exceeded)
-h/--help -- print this usage message and exit
-s/--socket-name SOCKET -- Unix socket name for client (default "zdsock")
-u/--user USER -- run as this user (or numeric uid)
-x/--exit-codes LIST -- list of fatal exit codes (default "0,2")
-z/--directory DIRECTORY -- directory to chdir to when using -d (default off)
program [program-arguments] -- an arbitrary application to run

This daemon manager has two purposes: it restarts the application when
it dies, and (when requested to do so with the -d option) it runs the
application in the background, detached from the foreground tty
session that started it (if any).

Exit codes: if at any point the application exits with an exit status
listed by the -x option, it is not restarted.  Any other form of
termination (either being killed by a signal or exiting with an exit
status not listed in the -x option) causes it to be restarted.

Backoff limit: when the application exits (nearly) immediately after a
restart, the daemon manager starts slowing down by delaying between
restarts.  The delay starts at 1 second and is increased by one on
each restart up to the backoff limit given by the -b option; it is
reset when the application runs for more than the backoff limit
seconds.  By default, when the delay reaches the backoff limit, the
daemon manager exits (under the assumption that the application has a
persistent fault).  The -f (forever) option prevents this exit; use it
when you expect that a temporary external problem (such as a network
outage or an overfull disk) may prevent the application from starting
but you want the daemon manager to keep trying.
"""

"""
XXX TO DO

- Finish OO design -- use multiple classes rather than folding
  everything into one class.

- Add unit tests.

- Add doc strings.

"""

import os
import sys
import time
import errno
import socket
import select
import getopt
import signal
from stat import ST_MODE

if __name__ == "__main__":
    # Add the parent of the script directory to the module search path
    # (but only when the script is run from inside the zdaemon package)
    from os.path import dirname, basename, abspath, normpath
    scriptdir = dirname(normpath(abspath(sys.argv[0])))
    if basename(scriptdir).lower() == "zdaemon":
        sys.path.append(dirname(scriptdir))

import ZConfig.datatypes
import zLOG
from zdaemon.zdoptions import RunnerOptions


class ZDRunOptions(RunnerOptions):

    positional_args_allowed = 1
    logsectionname = "eventlog"
    program = None

    def realize(self, *args, **kwds):
        RunnerOptions.realize(self, *args, **kwds)
        if self.args:
            self.program = self.args
        if not self.program:
            self.usage("no program specified (use -C or positional args)")
        if self.sockname:
            # Convert socket name to absolute path
            self.sockname = os.path.abspath(self.sockname)


class Subprocess:

    """A class to manage a subprocess."""

    # Initial state; overridden by instance variables
    pid = 0 # Subprocess pid; 0 when not running
    lasttime = 0 # Last time the subprocess was started; 0 if never

    def __init__(self, options, args=None):
        """Constructor.

        Arguments are a ZDRunOptions instance and a list of program
        arguments; the latter's first item must be the program name.
        """
        if args is None:
            args = options.args
        if not args:
            options.usage("missing 'program' argument")
        self.options = options
        self.args = args
        self._set_filename(args[0])

    def _set_filename(self, program):
        """Internal: turn a program name into a file name, using $PATH."""
        if "/" in program:
            filename = program
            try:
                st = os.stat(filename)
            except os.error:
                self.options.usage("can't stat program %r" % program)
        else:
            path = get_path()
            for dir in path:
                filename = os.path.join(dir, program)
                try:
                    st = os.stat(filename)
                except os.error:
                    continue
                mode = st[ST_MODE]
                if mode & 0111:
                    break
            else:
                self.options.usage("can't find program %r on PATH %s" %
                                   (program, path))
        if not os.access(filename, os.X_OK):
            self.options.usage("no permission to run program %r" % filename)
        self.filename = filename

    def spawn(self):
        """Start the subprocess.  It must not be running already.

        Return the process id.  If the fork() call fails, return 0.
        """
        assert not self.pid
        self.lasttime = time.time()
        try:
            pid = os.fork()
        except os.error:
            return 0
        if pid != 0:
            # Parent
            self.pid = pid
            info("spawned process pid=%d" % pid)
            return pid
        else:
            # Child
            try:
                # Close file descriptors except std{in,out,err}.
                # XXX We don't know how many to close; hope 100 is plenty.
                for i in range(3, 100):
                    try:
                        os.close(i)
                    except os.error:
                        pass
                try:
                    os.execv(self.filename, self.args)
                except os.error, err:
                    sys.stderr.write("can't exec %r: %s\n" %
                                     (self.filename, err))
            finally:
                os._exit(127)
            # Does not return

    def kill(self, sig):
        """Send a signal to the subprocess.  This may or may not kill it.

        Return None if the signal was sent, or an error message string
        if an error occurred or if the subprocess is not running.
        """
        if not self.pid:
            return "no subprocess running"
        try:
            os.kill(self.pid, sig)
        except os.error, msg:
            return str(msg)
        return None

    def setstatus(self, sts):
        """Set process status returned by wait() or waitpid().

        This simply notes the fact that the subprocess is no longer
        running by setting self.pid to 0.
        """
        self.pid = 0


class Daemonizer:

    def main(self, args=None):
        self.options = ZDRunOptions()
        self.options.realize(args)
        self.set_uid()
        self.run()

    def set_uid(self):
        if self.options.uid is None:
            return
        uid = os.geteuid()
        if uid != 0 and uid != self.options.uid:
            self.options.usage("only root can use -u USER to change users")
        os.setgid(self.options.gid)
        os.setuid(self.options.uid)

    def run(self):
        self.proc = Subprocess(self.options)
        self.opensocket()
        try:
            self.setsignals()
            if self.options.daemon:
                self.daemonize()
            self.runforever()
        finally:
            try:
                os.unlink(self.options.sockname)
            except os.error:
                pass

    mastersocket = None
    commandsocket = None

    def opensocket(self):
        sockname = self.options.sockname
        tempname = "%s.%d" % (sockname, os.getpid())
        self.unlink_quietly(tempname)
        while 1:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.bind(tempname)
                os.chmod(tempname, 0700)
                try:
                    os.link(tempname, sockname)
                    break
                except os.error:
                    # Lock contention, or stale socket.
                    self.checkopen()
                    # Stale socket -- delete, sleep, and try again.
                    msg = "Unlinking stale socket %s; sleep 1" % sockname
                    sys.stderr.write(msg + "\n")
                    warn(msg)
                    self.unlink_quietly(sockname)
                    sock.close()
                    time.sleep(1)
                    continue
            finally:
                self.unlink_quietly(tempname)
        sock.listen(1)
        sock.setblocking(0)
        self.mastersocket = sock

    def unlink_quietly(self, filename):
        try:
            os.unlink(filename)
        except os.error:
            pass

    def checkopen(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.connect(self.options.sockname)
            s.send("status\n")
            data = s.recv(1000)
            s.close()
        except socket.error:
            pass
        else:
            while data.endswith("\n"):
                data = data[:-1]
            msg = ("Another zrdun is already up using socket %r:\n%s" %
                   (self.options.sockname, data))
            sys.stderr.write(msg + "\n")
            critical(msg)
            sys.exit(1)

    def setsignals(self):
        signal.signal(signal.SIGTERM, self.sigexit)
        signal.signal(signal.SIGHUP, self.sigexit)
        signal.signal(signal.SIGINT, self.sigexit)
        signal.signal(signal.SIGCHLD, self.sigchild)

    def sigexit(self, sig, frame):
        critical("daemon manager killed by %s" % signame(sig))
        sys.exit(1)

    waitstatus = None

    def sigchild(self, sig, frame):
        try:
            pid, sts = os.waitpid(-1, os.WNOHANG)
        except os.error:
            return
        if pid:
            self.waitstatus = pid, sts

    def daemonize(self):

        # To daemonize, we need to become the leader of our own session
        # (process) group.  If we do not, signals sent to our
        # parent process will also be sent to us.   This might be bad because
        # signals such as SIGINT can be sent to our parent process during
        # normal (uninteresting) operations such as when we press Ctrl-C in the
        # parent terminal window to escape from a logtail command.
        # To disassociate ourselves from our parent's session group we use
        # os.setsid.  It means "set session id", which has the effect of
        # disassociating a process from is current session and process group
        # and setting itself up as a new session leader.
        #
        # Unfortunately we cannot call setsid if we're already a session group
        # leader, so we use "fork" to make a copy of ourselves that is
        # guaranteed to not be a session group leader.
        #
        # We also change directories, set stderr and stdout to null, and
        # change our umask.
        #
        # This explanation was (gratefully) garnered from
        # http://www.hawklord.uklinux.net/system/daemons/d3.htm

        pid = os.fork()
        if pid != 0:
            # Parent
            debug("daemon manager forked; parent exiting")
            os._exit(0)
        # Child
        info("daemonizing the process")
        if self.options.directory:
            try:
                os.chdir(self.options.directory)
            except os.error, err:
                warn("can't chdir into %r: %s" %
                     (self.options.directory, err))
            else:
                info("set current directory: %r" % self.options.directory)
        os.close(0)
        sys.stdin = sys.__stdin__ = open("/dev/null")
        os.close(1)
        sys.stdout = sys.__stdout__ = open("/dev/null", "w")
        os.close(2)
        sys.stderr = sys.__stderr__ = open("/dev/null", "w")
        os.setsid()
        os.umask(022) # Create no group/other writable files/directories
        # XXX Stevens, in his Advanced Unix book, section 13.3 (page
        # 417) recommends calling umask(0) and closing unused
        # file descriptors.  In his Network Programming book, he
        # additionally recommends ignoring SIGHUP and forking again
        # after the setsid() call, for obscure SVR4 reasons.

    mood = 1 # 1: up, 0: down, -1: suicidal
    delay = 0 # If nonzero, delay starting or killing until this time
    killing = 0 # If true, send SIGKILL when delay expires
    proc = None # Subprocess instance

    def runforever(self):
        info("daemon manager started")
        min_mood = not self.options.hang_around
        while self.mood >= min_mood or self.proc.pid:
            if self.mood > 0 and not self.proc.pid and not self.delay:
                pid = self.proc.spawn()
                if not pid:
                    # Can't fork.  Try again later...
                    self.delay = time.time() + self.backofflimit
            if self.waitstatus:
                self.reportstatus()
            r, w, x = [self.mastersocket], [], []
            if self.commandsocket:
                r.append(self.commandsocket)
            timeout = self.options.backofflimit
            if self.delay:
                timeout = max(0, min(timeout, self.delay - time.time()))
                if timeout <= 0:
                    self.delay = 0
                    if self.killing and self.proc.pid:
                        self.proc.kill(signal.SIGKILL)
                        self.delay = time.time() + self.options.backofflimit
            try:
                r, w, x = select.select(r, w, x, timeout)
            except select.error, err:
                if err[0] != errno.EINTR:
                    raise
                r = w = x = []
            if self.waitstatus:
                self.reportstatus()
            if self.commandsocket and self.commandsocket in r:
                try:
                    self.dorecv()
                except socket.error, msg:
                    exception("socket.error in dorecv(): %s" % str(msg))
                    self.commandsocket = None
            if self.mastersocket in r:
                try:
                    self.doaccept()
                except socket.error, msg:
                    exception("socket.error in doaccept(): %s" % str(msg))
                    self.commandsocket = None
        info("Exiting")
        sys.exit(0)

    def reportstatus(self):
        pid, sts = self.waitstatus
        self.waitstatus = None
        es, msg = decode_wait_status(sts)
        msg = "pid %d: " % pid + msg
        if pid != self.proc.pid:
            msg = "unknown " + msg
            warn(msg)
        else:
            killing = self.killing
            if killing:
                self.killing = 0
                self.delay = 0
            else:
                self.governor()
            self.proc.setstatus(sts)
            if es in self.options.exitcodes and not killing:
                msg = msg + "; exiting now"
                info(msg)
                sys.exit(es)
            info(msg)

    backoff = 0

    def governor(self):
        # Back off if respawning too frequently
        now = time.time()
        if not self.proc.lasttime:
            pass
        elif now - self.proc.lasttime < self.options.backofflimit:
            # Exited rather quickly; slow down the restarts
            self.backoff += 1
            if self.backoff >= self.options.backofflimit:
                if self.options.forever:
                    self.backoff = self.options.backofflimit
                else:
                    critical("restarting too frequently; quit")
                    sys.exit(1)
            info("sleep %s to avoid rapid restarts" % self.backoff)
            self.delay = now + self.backoff
        else:
            # Reset the backoff timer
            self.backoff = 0
            self.delay = 0

    def doaccept(self):
        if self.commandsocket:
            # Give up on previous command socket!
            self.sendreply("Command superseded by new command")
            self.commandsocket.close()
            self.commandsocket = None
        self.commandsocket, addr = self.mastersocket.accept()
        self.commandbuffer = ""

    def dorecv(self):
        data = self.commandsocket.recv(1000)
        if not data:
            self.sendreply("Command not terminated by newline")
            self.commandsocket.close()
            self.commandsocket = None
        self.commandbuffer += data
        if "\n" in self.commandbuffer:
            self.docommand()
            self.commandsocket.close()
            self.commandsocket = None
        elif len(self.commandbuffer) > 10000:
            self.sendreply("Command exceeds 10 KB")
            self.commandsocket.close()
            self.commandsocket = None

    def docommand(self):
        lines = self.commandbuffer.split("\n")
        args = lines[0].split()
        if not args:
            self.sendreply("Empty command")
            return
        command = args[0]
        methodname = "cmd_" + command
        method = getattr(self, methodname, None)
        if method:
            method(args)
        else:
            self.sendreply("Unknown command %r; 'help' for a list" % args[0])

    def cmd_start(self, args):
        self.mood = 1 # Up
        self.backoff = 0
        self.delay = 0
        self.killing = 0
        if not self.proc.pid:
            self.proc.spawn()
            self.sendreply("Application started")
        else:
            self.sendreply("Application already started")

    def cmd_stop(self, args):
        self.mood = 0 # Down
        self.backoff = 0
        self.delay = 0
        self.killing = 0
        if self.proc.pid:
            self.proc.kill(signal.SIGTERM)
            self.sendreply("Sent SIGTERM")
            self.killing = 1
            self.delay = time.time() + self.options.backofflimit
        else:
            self.sendreply("Application already stopped")

    def cmd_restart(self, args):
        self.mood = 1 # Up
        self.backoff = 0
        self.delay = 0
        self.killing = 0
        if self.proc.pid:
            self.proc.kill(signal.SIGTERM)
            self.sendreply("Sent SIGTERM; will restart later")
            self.killing = 1
            self.delay = time.time() + self.options.backofflimit
        else:
            self.proc.spawn()
            self.sendreply("Application started")

    def cmd_exit(self, args):
        self.mood = -1 # Suicidal
        self.backoff = 0
        self.delay = 0
        self.killing = 0
        if self.proc.pid:
            self.proc.kill(signal.SIGTERM)
            self.sendreply("Sent SIGTERM; will exit later")
            self.killing = 1
            self.delay = time.time() + self.options.backofflimit
        else:
            self.sendreply("Exiting now")
            info("Exiting")
            sys.exit(0)

    def cmd_kill(self, args):
        if args[1:]:
            try:
                sig = int(args[1])
            except:
                self.sendreply("Bad signal %r" % args[1])
                return
        else:
            sig = signal.SIGTERM
        if not self.proc.pid:
            self.sendreply("Application not running")
        else:
            msg = self.proc.kill(sig)
            if msg:
                self.sendreply("Kill %d failed: %s" % (sig, msg))
            else:
                self.sendreply("Signal %d sent" % sig)

    def cmd_status(self, args):
        if not self.proc.pid:
            status = "stopped"
        else:
            status = "running"
        self.sendreply("status=%s\n" % status +
                       "now=%r\n" % time.time() +
                       "mood=%d\n" % self.mood +
                       "delay=%r\n" % self.delay +
                       "backoff=%r\n" % self.backoff +
                       "lasttime=%r\n" % self.proc.lasttime +
                       "application=%r\n" % self.proc.pid +
                       "manager=%r\n" % os.getpid() +
                       "backofflimit=%r\n" % self.options.backofflimit +
                       "filename=%r\n" % self.proc.filename +
                       "args=%r\n" % self.proc.args)

    def cmd_help(self, args):
        self.sendreply(
            "Available commands:\n"
            "  help -- return command help\n"
            "  status -- report application status (default command)\n"
            "  kill [signal] -- send a signal to the application\n"
            "                   (default signal is SIGTERM)\n"
            "  start -- start the application if not already running\n"
            "  stop -- stop the application if running\n"
            "          (the daemon manager keeps running)\n"
            "  restart -- stop followed by start\n"
            "  exit -- stop the application and exit\n"
            )

    def sendreply(self, msg):
        try:
            if not msg.endswith("\n"):
                msg = msg + "\n"
            if hasattr(self.commandsocket, "sendall"):
                self.commandsocket.sendall(msg)
            else:
                # This is quadratic, but msg is rarely more than 100 bytes :-)
                while msg:
                    sent = self.commandsocket.send(msg)
                    msg = msg[sent:]
        except socket.error, msg:
            warn("Error sending reply: %s" % str(msg))

# Log messages with various severities.
# This uses zLOG, but the API is a simplified version of PEP 282

def critical(msg):
    """Log a critical message."""
    _log(msg, zLOG.PANIC)

def error(msg):
    """Log an error message."""
    _log(msg, zLOG.ERROR)

def exception(msg):
    """Log an exception (an error message with a traceback attached)."""
    _log(msg, zLOG.ERROR, error=sys.exc_info())

def warn(msg):
    """Log a warning message."""
    _log(msg, zLOG.PROBLEM)

def info(msg):
    """Log an informational message."""
    _log(msg, zLOG.INFO)

def debug(msg):
    """Log a debugging message."""
    _log(msg, zLOG.DEBUG)

def _log(msg, severity=zLOG.INFO, error=None):
    """Internal: generic logging function."""
    zLOG.LOG("ZD:%d" % os.getpid(), severity, msg, "", error)

# Helpers for dealing with signals and exit status

def decode_wait_status(sts):
    """Decode the status returned by wait() or waitpid().

    Return a tuple (exitstatus, message) where exitstatus is the exit
    status, or -1 if the process was killed by a signal; and message
    is a message telling what happened.  It is the caller's
    responsibility to display the message.
    """
    if os.WIFEXITED(sts):
        es = os.WEXITSTATUS(sts) & 0xffff
        msg = "exit status %s" % es
        return es, msg
    elif os.WIFSIGNALED(sts):
        sig = os.WTERMSIG(sts)
        msg = "terminated by %s" % signame(sig)
        if hasattr(os, "WCOREDUMP"):
            iscore = os.WCOREDUMP(sts)
        else:
            iscore = sts & 0x80
        if iscore:
            msg += " (core dumped)"
        return -1, msg
    else:
        msg = "unknown termination cause 0x%04x" % sts
        return -1, msg

_signames = None

def signame(sig):
    """Return a symbolic name for a signal.

    Return "signal NNN" if there is no corresponding SIG name in the
    signal module.
    """

    if _signames is None:
        _init_signames()
    return _signames.get(sig) or "signal %d" % sig

def _init_signames():
    global _signames
    d = {}
    for k, v in signal.__dict__.items():
        k_startswith = getattr(k, "startswith", None)
        if k_startswith is None:
            continue
        if k_startswith("SIG") and not k_startswith("SIG_"):
            d[v] = k
    _signames = d

def get_path():
    """Return a list corresponding to $PATH, or a default."""
    path = ["/bin", "/usr/bin", "/usr/local/bin"]
    if os.environ.has_key("PATH"):
        p = os.environ["PATH"]
        if p:
            path = p.split(os.pathsep)
    return path

# Main program
def main(args=None):
    assert os.name == "posix", "This code makes many Unix-specific assumptions"

    zLOG.initialize()
    d = Daemonizer()
    d.main(args)

if __name__ == "__main__":
    main()
