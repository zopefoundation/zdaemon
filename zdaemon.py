#! /usr/bin/env python

"""
zdaemon -- run an application as a daemon.

Usage: python zdaemon.py [zdaemon-options] program [program-arguments]
Or:    python zdaemon.py -c [command]

Options:
  -b SECONDS -- set backoff limit to SECONDS (default 10; see below)
  -c -- client mode, to sends a command to the daemon manager; see below
  -d -- run as a proper daemon; fork a background process, close files etc.
  -f -- run forever (by default, exit when the backoff limit is exceeded)
  -h -- print usage message and exit
  -s SOCKET -- Unix socket name for client communication (default "zdsock")
  -u USER -- run as this user (or numeric uid)
  -x LIST -- list of fatal exit codes (default "0,2"; use "" to disable)
  -z DIRECTORY -- directory to chdir into when using -d; default "/"
  program [program-arguments] -- an arbitrary application to run

Client mode options:
  -s SOCKET -- socket name (a Unix pathname) for client communication
  [command] -- the command to send to the daemon manager (default "status")

Client commands are:
  help -- return command help
  status -- report application status (this is the default command)
  kill [signal] -- send a signal to the application
                   (default signal is SIGTERM)
  start -- start the application if not already running
  stop -- stop the application if running; daemon manager keeps running
  restart -- stop followed by start
  exit -- stop the application and exit

This daemon manager has two purposes: it restarts the application when
it dies, and (when requested to do so with the -d option) it runs the
application in the background, detached from the foreground tty
session that started it (if any).

Important: if at any point the application exits with an exit status
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

- True OO design -- use multiple classes rather than folding
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
    from os.path import dirname, abspath, normpath
    sys.path.append(dirname(dirname(normpath(abspath(sys.argv[0])))))

import zLOG

class Options:

    """A class to parse and hold the command line options.

    Options are represented by various attributes (backofflimit etc.).
    Positional arguments are represented by the args attribute.

    This also has a public usage() method that can be used to report
    errors related to the command line.
    """

    progname = "zdaemon.py"             # Program name for usage message

    # Options we know of, and their defaults
    backofflimit = 10                   # -b SECONDS
    isclient = 0                        # -c
    daemon = 0                          # -d
    forever = 0                         # -f
    sockname = "zdsock"                 # -s SOCKET
    exitcodes = [0, 2]                  # -x LIST
    user = None                         # -u USER
    zdirectory = "/"                    # -z DIRECTORY

    args = []                           # Positional arguments

    def __init__(self, args=None, progname=None):
        """Constructor.

        Optional arguments:

        args     -- the command line arguments, less the program name
                    (default is sys.argv[1:] at the time of call)

        progname -- the program name (default "zdaemon.py")
        """

        if args is None:
            args = sys.argv[1:]
        if progname:
            self.progname = progname
        try:
            self.options, self.args = getopt.getopt(args, "b:cdfhs:u:x:z:")
        except getopt.error, msg:
            self.usage(str(msg))
        self._interpret_options()

    def _interpret_options(self):
        """Internal: interpret the options parsed by getopt.getopt().

        This sets the various instance variables overriding the defaults.

        When -h is detected, print the module docstring to stdout and exit(0).
        """
        for o, a in self.options:
            # Keep these in alphabetical order please!
            if o == "-b":
                try:
                    self.backofflimit = float(a)
                except:
                    self.usage("invalid number: %r" % a)
            if o == "-c":
                self.isclient += 1
            if o == "-d":
                self.daemon += 1
            if o == "-f":
                self.forever += 1
            if o == "-h":
                print __doc__,
                sys.exit(0)
            if o == "-s":
                self.sockname = a
            if o == "-u":
                self.user = a
            if o == "-x":
                if a == "":
                    self.exitcodes = []
                else:
                    try:
                        self.exitcodes = map(int, a.split(","))
                    except:
                        self.usage("list of ints required: %r" % a)
            if o == "-z":
                self.zdirectory = a

    def usage(self, msg):
        """Write an error message to stderr and exit(2)."""
        sys.stderr.write("Error: %s\n" % str(msg))
        sys.stderr.write("For help, use %s -h\n" % self.progname)
        sys.exit(2)

class Subprocess:

    """A class to manage a subprocess."""

    # Initial state; overridden by instance variables
    pid = 0 # Subprocess pid; 0 when not running
    lasttime = 0 # Last time the subprocess was started; 0 if never

    def __init__(self, options, args=None):
        """Constructor.

        Arguments are an Options instance and a list of program
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

class Client:

    """A class representing the control client."""

    def __init__(self, options, args=None):
        """Constructor.

        Arguments are an Options instance and a list of program
        arguments representing the command to send to the server.
        """
        self.options = options
        if args is None:
            args = options.args
        if not args:
            self.command = "status"
        else:
            self.command = " ".join(args)

    def doit(self):
        """Send the command to the server and write the results to stdout."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self.options.sockname)
        except socket.error, msg:
            sys.stderr.write("Can't connect to %r: %s\n" %
                             (self.options.sockname, msg))
            sys.exit(1)
        sock.send(self.command + "\n")
        sock.shutdown(1) # We're not writing any more
        lastdata = ""
        while 1:
            data = sock.recv(1000)
            if not data:
                break
            sys.stdout.write(data)
            lastdata = data
        if not lastdata:
            sys.stderr.write("No response received\n")
            sys.exit(1)
        if not lastdata.endswith("\n"):
            sys.stdout.write("\n")

class Daemonizer:

    def main(self, args=None):
        self.options = Options(args)
        self.set_uid()
        if self.options.isclient:
            clt = Client(self.options)
            clt.doit()
        else:
            self.run()

    def set_uid(self):
        if self.options.user is None:
            return
        if os.name != "posix":
            self.options.usage("-u USER only supported on Unix")
        if os.geteuid() != 0:
            self.options.usage("only root can use -u USER")
        import pwd
        try:
            uid = int(self.options.user)
        except: # int() can raise all sorts of errors
            try:
                pwrec = pwd.getpwnam(self.options.user)
            except KeyError:
                self.options.usage("username %r not found" % self.options.user)
            uid = pwrec[2]
        else:
            try:
                pwrec = pwd.getpwuid(uid)
            except KeyError:
                self.options.usage("uid %r not found" % self.options.user)
        gid = pwrec[3]
        os.setgid(gid)
        os.setuid(uid)

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
        self.checkopen()
        try:
            os.unlink(self.options.sockname)
        except os.error:
            pass
        self.mastersocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        oldumask = None
        try:
            oldumask = os.umask(077)
            self.mastersocket.bind(self.options.sockname)
        finally:
            if oldumask is not None:
                os.umask(oldumask)
        self.mastersocket.listen(1)
        self.mastersocket.setblocking(0)

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
            if not data.endswith("\n"):
                data += "\n"
            msg = ("Another zdaemon is already up using socket %r:\n%s" %
                   (self.options.sockname, data))
            sys.stderr.write(msg)
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
        pid = os.fork()
        if pid != 0:
            # Parent
            debug("daemon manager forked; parent exiting")
            os._exit(0)
        # Child
        info("daemonizing the process")
        if self.options.zdirectory:
            try:
                os.chdir(self.options.zdirectory)
            except os.error, err:
                warn("can't chdir into %r: %s" %
                     (self.options.zdirectory, err))
            else:
                info("set current directory: %r" % self.options.zdirectory)
        os.close(0)
        sys.stdin = sys.__stdin__ = open("/dev/null")
        os.close(1)
        sys.stdout = sys.__stdout__ = open("/dev/null", "w")
        os.close(2)
        sys.stderr = sys.__stderr__ = open("/dev/null", "w")
        os.setsid()

    mood = 1 # 1: up, 0: down, -1: suicidal
    delay = 0 # If nonzero, delay starting or killing until this time
    killing = 0 # If true, send SIGKILL when delay expires
    proc = None # Subprocess instance

    def runforever(self):
        info("daemon manager started")
        while self.mood >= 0 or self.proc.pid:
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
            if self.killing:
                self.killing = 0
                self.delay = 0
            else:
                self.governor()
            self.proc.setstatus(sts)
            if es in self.options.exitcodes:
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
    d = Daemonizer()
    d.main(args)

if __name__ == "__main__":
    main()
