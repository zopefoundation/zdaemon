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

Important: if at any point the application exits with exit status 0 or
2, it is not restarted.  Any other form of termination (either being
killed by a signal or exiting with an exit status other than 0 or 2)
causes it to be restarted.

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

- Rethink client commands; maybe start/restart/stop make more sense?
  (Still need a way to send an arbitrary signal)

- Do the governor without actual sleeps, using event scheduling etc.

- True OO design -- use multiple classes rather than folding
  everything into one class.

- Add docstrings.

"""

import os
assert os.name == "posix", "This code makes many Unix-specific assumptions"
import sys
import time
import errno
import socket
import select
import getopt
import signal
from stat import ST_MODE

import zLOG

class Daemonizer:

    # Settable options
    daemon = 0
    forever = 0
    backofflimit = 10
    sockname = "zdsock"
    isclient = 0

    def __init__(self):
        self.filename = None
        self.args = []

    def main(self, args=None):
        self.prepare(args)
        self.run()

    def prepare(self, args=None):
        if args is None:
            args = sys.argv[1:]
        self.blather("args=%s" % repr(args))
        try:
            opts, args = getopt.getopt(args, "b:cdfhs:")
        except getopt.error, msg:
            self.usage(str(msg))
        self.parseoptions(opts)
        if self.isclient:
            self.setcommand(args)
        else:
            self.setprogram(args)

    def parseoptions(self, opts):
        self.info("opts=%s" % repr(opts))
        for o, a in opts:
            # Alphabetical order please!
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
                self.exit()
            if o == "-s":
                self.sockname = a

    def setcommand(self, args):
        if not args:
            self.command = "status"
        else:
            self.command = " ".join(args)

    def sendcommand(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self.sockname)
        except socket.error, msg:
            self.errwrite("Can't connect to %r: %s\n" % (self.sockname, msg))
            self.exit(1)
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
            self.errwrite("No response received\n")
            self.exit(1)
        if not lastdata.endswith("\n"):
            sys.stdout.write("\n")

    def setprogram(self, args):
        if not args:
            self.usage("missing 'program' argument")
        self.filename = self.checkcommand(args[0])
        self.args = args # A list of strings like for execvp()
        self.info("filename=%r; args=%r" % (self.filename, self.args))

    def checkcommand(self, command):
        if "/" in command:
            filename = command
            try:
                st = os.stat(filename)
            except os.error:
                self.usage("can't stat program %r" % command)
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
                self.usage("can't find program %r on PATH %s" %
                           (command, path))
        if not os.access(filename, os.X_OK):
            self.usage("no permission to run program %r" % filename)
        return filename

    def getpath(self):
        path = ["/bin", "/usr/bin", "/usr/local/bin"]
        if os.environ.has_key("PATH"):
            p = os.environ["PATH"]
            if p:
                path = p.split(os.pathsep)
        return path

    def run(self):
        if self.isclient:
            self.sendcommand()
            return
        self.opensocket()
        try:
            self.setsignals()
            if self.daemon:
                self.daemonize()
            self.runforever()
        finally:
            try:
                os.unlink(self.sockname)
            except os.error:
                pass

    mastersocket = None
    commandsocket = None

    def opensocket(self):
        self.checkopen()
        try:
            os.unlink(self.sockname)
        except os.error:
            pass
        self.mastersocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        oldumask = None
        try:
            oldumask = os.umask(077)
            self.mastersocket.bind(self.sockname)
        finally:
            if oldumask is not None:
                os.umask(oldumask)
        self.mastersocket.listen(1)
        self.mastersocket.setblocking(0)

    def checkopen(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.connect(self.sockname)
            s.send("status\n")
            data = s.recv(1000)
            s.close()
        except socket.error:
            pass
        else:
            if not data.endswith("\n"):
                data += "\n"
            msg = ("Another zdaemon is already up using socket %r:\n%s" %
                   (self.sockname, data))
            self.errwrite(msg)
            self.panic(msg)
            self.exit(1)

    def setsignals(self):
        signal.signal(signal.SIGTERM, self.sigexit)
        signal.signal(signal.SIGHUP, self.sigexit)
        signal.signal(signal.SIGINT, self.sigexit)
        signal.signal(signal.SIGCHLD, self.sigchild)

    def sigexit(self, sig, frame):
        self.info("daemon manager killed by %s" % self.signame(sig))
        self.exit(1)

    waitstatus = None

    def sigchild(self, sig, frame):
        pid, sts = os.waitpid(-1, os.WNOHANG)
        if pid:
            self.waitstatus = pid, sts

    def daemonize(self):
        pid = os.fork()
        if pid != 0:
            # Parent
            self.blather("daemon manager forked; parent exiting")
            os._exit(0)
        # Child
        self.info("daemonizing the process")
        os.chdir("/")
        os.close(0)
        sys.stdin = sys.__stdin__ = open("/dev/null")
        os.close(1)
        sys.stdout = sys.__stdout__ = open("/dev/null", "w")
        os.close(2)
        sys.stderr = sys.__stderr__ = open("/dev/null", "w")
        os.setsid()

    mood = 1 # 1: up, 0: down, -1: suicidal
    appid = 0 # Application pid; indicates status (0 == not running)

    def runforever(self):
        self.info("daemon manager started")
        while self.mood >= 0 or self.appid:
            if self.mood > 0 and not self.appid:
                self.forkandexec()
            if self.waitstatus:
                self.reportstatus()
            r, w, x = [self.mastersocket], [], []
            if self.commandsocket:
                r.append(self.commandsocket)
            timeout = self.backofflimit
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
                    self.problem("socket.error in dorecv(): %s" % str(msg),
                                 error=sys.exc_info())
                    self.commandsocket = None
            if self.mastersocket in r:
                try:
                    self.doaccept()
                except socket.error, msg:
                    self.problem("socket.error in doaccept(): %s" % str(msg),
                                 error=sys.exc_info())
                    self.commandsocket = None
        self.info("Exiting")
        self.exit(0)

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
        if not self.appid:
            self.forkandexec()
            self.sendreply("Application started")
        else:
            self.sendreply("Application already started")

    def cmd_stop(self, args):
        self.mood = 0 # Down
        if self.appid:
            os.kill(self.appid, signal.SIGTERM)
            self.sendreply("Sent SIGTERM")
        else:
            self.sendreply("Application already stopped")

    def cmd_restart(self, args):
        self.mood = 1 # Up
        if self.appid:
            os.kill(self.appid, signal.SIGTERM)
            self.sendreply("Sent SIGTERM; will restart later")
        else:
            self.forkandexec()
            self.sendreply("Application started")

    def cmd_exit(self, args):
        self.mood = -1 # Suicidal
        if self.appid:
            os.kill(self.appid, signal.SIGTERM)
            self.sendreply("Sent SIGTERM; will exit later")
        else:
            self.sendreply("Exiting now")
            self.info("Exiting")
            self.exit(0)

    def cmd_kill(self, args):
        if args[1:]:
            try:
                sig = int(args[1])
            except:
                self.sendreply("Bad signal %r" % args[1])
                return
        else:
            sig = signal.SIGTERM
        if not self.appid:
            self.sendreply("Application not running")
        else:
            try:
                os.kill(self.appid, sig)
            except os.error, msg:
                self.sendreply("Kill %d failed: %s" % (sig, msg))
            else:
                self.sendreply("Signal %d sent" % sig)

    def cmd_status(self, args):
        if not self.appid:
            status = "stopped"
        else:
            status = "running"
        self.sendreply("status=%s\n" % status +
                       "manager=%d\n" % os.getpid() + 
                       "application=%d\n" % self.appid +
                       "filename=%r\n" % self.filename +
                       "args=%r\n" % self.args)

    def cmd_help(self, args):
        self.sendreply(
            "Available commands:\n"
            "  help -- return command help\n"
            "  status -- report application status (default command)\n"
            "  kill [signal] -- send a signal to the application\n"
            "                   (default signal is SIGTERM)\n"
            "start -- start the application if not already running\n"
            "stop -- stop the application if running\n"
            "        (the daemon manager keeps running)\n"
            "restart -- stop followed by start\n"
            "exit -- stop the application and exit\n"
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
            self.problem("Error sending reply: %s" % str(msg))

    backoff = 0
    lasttime = None

    def governor(self):
        # Back off if respawning too often
        if not self.lasttime:
            pass
        elif time.time() - self.lasttime < self.backofflimit:
            # Exited rather quickly; slow down the restarts
            self.backoff += 1
            if self.backoff >= self.backofflimit:
                if self.forever:
                    self.backoff = self.backofflimit
                else:
                    self.error("restarting too often; quit")
                    self.exit(1)
            self.info("sleep %s to avoid rapid restarts" % self.backoff)
            time.sleep(self.backoff)
        else:
            # Reset the backoff timer
            self.backoff = 0
        self.lasttime = time.time()

    def forkandexec(self):
        self.governor()
        pid = os.fork()
        if pid != 0:
            # Parent
            self.appid = pid
            self.info("forked child pid %d" % pid)
        else:
            # Child
            self.startprogram()

    def startprogram(self):
        try:
            if self.commandsocket:
                self.commandsocket.close()
            if self.mastersocket:
                self.mastersocket.close()
            self.blather("about to exec %s" % self.filename)
            try:
                os.execv(self.filename, self.args)
            except os.error, err:
                self.panic("can't exec %r: %s" % (self.filename, err))
        finally:
            os._exit(127)

    def reportstatus(self):
        pid, sts = self.waitstatus
        self.waitstatus = None
        if pid == self.appid:
            self.appid = 0
        if os.WIFEXITED(sts):
            es = os.WEXITSTATUS(sts)
            msg = "pid %d: exit status %s" % (pid, es)
            if es == 0:
                self.info(msg)
                self.exit(0)
            elif es == 2:
                self.error(msg)
                self.exit(es)
            else:
                self.problem(msg)
        elif os.WIFSIGNALED(sts):
            sig = os.WTERMSIG(sts)
            msg = ("pid %d: terminated by %s" % (pid, self.signame(sig)))
            if hasattr(os, "WCOREDUMP"):
                iscore = os.WCOREDUMP(sts)
            else:
                iscore = s & 0x80
            if iscore:
                msg += " (core dumped)"
            self.problem(msg)
        else:
            msg = "pid %d: unknown termination cause 0x%04x" % (pid, sts)
            self.problem(msg)

    signames = None

    def signame(self, sig):
        """Return the symbolic name for signal sig.

        Returns 'unknown' if there is no SIG name bound to sig in the
        signal module.
        """

        if self.signames is None:
            self.setupsignames()
        return self.signames.get(sig) or "signal %d" % sig

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
        self.error(str(msg))
        self.errwrite("Error: %s\n" % str(msg))
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

    def problem(self, msg):
        self.log(msg, zLOG.PROBLEM)

    def error(self, msg, error=None):
        self.log(msg, zLOG.ERROR, error)

    def panic(self, msg, error=None):
        self.log(msg, zLOG.PANIC, error)

    def getsubsystem(self):
        return "ZD:%d" % os.getpid()

    def log(self, msg, severity=zLOG.INFO, error=None):
        zLOG.LOG(self.getsubsystem(), severity, msg, "", error)

def main(args=None):
    d = Daemonizer()
    d.main(args)

if __name__ == "__main__":
    main()
