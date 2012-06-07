#!python
##############################################################################
#
# Copyright (c) 2001, 2002 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""zdctl -- control an application run by zdaemon.

Usage: python zdctl.py [-C URL] [-S schema.xml] [-h] [-p PROGRAM]
       [zdrun-options] [action [arguments]]

Options:
-b/--backoff-limit SECONDS -- set backoff limit to SECONDS (default 10)
-C/--configure URL -- configuration file or URL
-d/--daemon -- run as a proper daemon; fork a subprocess, close files etc.
-f/--forever -- run forever (by default, exit when backoff limit is exceeded)
-h/--help -- print this usage message and exit
-l/--logfile -- log file to be read by logtail command
-p/--program PROGRAM -- the program to run
-S/--schema XML Schema -- XML schema for configuration file
-T/--start-timeout SECONDS -- Start timeout when a test program is used
-s/--socket-name SOCKET -- Unix socket name for client (default "zdsock")
-u/--user USER -- run as this user (or numeric uid)
-m/--umask UMASK -- use this umask for daemon subprocess (default is 022)
-x/--exit-codes LIST -- list of fatal exit codes (default "0,2")
-z/--directory DIRECTORY -- directory to chdir to when using -d (default off)
action [arguments] -- see below

Actions are commands like "start", "stop" and "status".  Use the
action "help" to find out about available actions.
"""

import os
import os.path
import re
import cmd
import sys
import time
import signal
import socket
import stat

if __name__ == "__main__":
    # Add the parent of the script directory to the module search path
    # (but only when the script is run from inside the zdaemon package)
    from os.path import dirname, basename, abspath, normpath
    scriptdir = dirname(normpath(abspath(sys.argv[0])))
    if basename(scriptdir).lower() == "zdaemon":
        sys.path.append(dirname(scriptdir))
    here = os.path.dirname(os.path.realpath(__file__))
    swhome = os.path.dirname(here)
    for parts in [("src",), ("lib", "python"), ("Lib", "site-packages")]:
        d = os.path.join(swhome, *(parts + ("zdaemon",)))
        if os.path.isdir(d):
            d = os.path.join(swhome, *parts)
            sys.path.insert(0, d)
            break

from zdaemon.zdoptions import RunnerOptions


def string_list(arg):
    return arg.split()


class ZDCtlOptions(RunnerOptions):

    __doc__ = __doc__

    positional_args_allowed = True

    def __init__(self):
        RunnerOptions.__init__(self)
        self.add("schemafile", short="S:", long="schema=",
                 default="schema.xml",
                 handler=self.set_schemafile)
        self.add("program", "runner.program", "p:", "program=",
                 handler=string_list,
                 required="no program specified; use -p or -C")
        self.add("logfile", "runner.logfile", "l:", "logfile=")
        self.add("start_timeout", "runner.start_timeout",
                 "T:", "start-timeout=", int, default=300)
        self.add("python", "runner.python")
        self.add("zdrun", "runner.zdrun")
        programname = os.path.basename(sys.argv[0])
        base, ext = os.path.splitext(programname)
        if ext == ".py":
            programname = base
        self.add("prompt", "runner.prompt", default=(programname + ">"))

    def realize(self, *args, **kwds):

        RunnerOptions.realize(self, *args, **kwds)

        # Maybe the config file requires -i or positional args
        if not self.args:
            self.usage("an action argument is required")

        # Where's python?
        if not self.python:
            self.python = sys.executable

    def set_schemafile(self, file):
        self.schemafile = file



class ZDCmd(cmd.Cmd):

    def __init__(self, options):
        self.options = options
        self.prompt = self.options.prompt + ' '
        cmd.Cmd.__init__(self)
        self.get_status()
        if self.zd_status:
            m = re.search("(?m)^args=(.*)$", self.zd_status)
            if m:
                s = m.group(1)
                args = eval(s, {"__builtins__": {}})
                program = self.options.program
                if args[:len(program)] != program:
                    print "WARNING! zdrun is managing a different program!"
                    print "our program   =", program
                    print "daemon's args =", args

        if options.configroot is not None:
            env = getattr(options.configroot, 'environment', None)
            if env is not None:
                if getattr(env, 'mapping', None) is not None:
                    for k, v in env.mapping.items():
                        os.environ[k] = v
                elif type(env) is type({}):
                    for k, v in env.items():
                        os.environ[k] = v

        self.create_rundir()
        self.create_socket_dir()
        self.set_uid()

    def create_rundir(self):
        if self.options.directory is None:
            return
        self.create_directory(self.options.directory)

    def create_socket_dir(self):
        dir = os.path.dirname(self.options.sockname)
        if not dir:
            return
        self.create_directory(dir)

    def create_directory(self, directory):
        if os.path.isdir(directory):
            return
        os.mkdir(directory)
        uid = os.geteuid()
        if uid == 0 and uid != self.options.uid:
            # Change owner of directory to target
            os.chown(directory, self.options.uid, self.options.gid)

    def set_uid(self):
        if self.options.uid is None:
            return
        uid = os.geteuid()
        if uid != 0 and uid != self.options.uid:
            self.options.usage("only root can use -u USER to change users")
        os.setgid(self.options.gid)
        os.setgroups(self.options.groups)
        os.setuid(self.options.uid)

    def emptyline(self):
        # We don't want a blank line to repeat the last command.
        # Showing status is a nice alternative.
        self.do_status()

    def send_action(self, action):
        """Send an action to the zdrun server and return the response.

        Return None if the server is not up or any other error happened.
        """
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self.options.sockname)
            sock.send(action + "\n")
            sock.shutdown(1) # We're not writing any more
            response = ""
            while 1:
                data = sock.recv(1000)
                if not data:
                    break
                response += data
            sock.close()
            return response
        except socket.error, msg:
            return None

    zd_testing = 0
    def get_status(self):
        self.zd_up = 0
        self.zd_pid = 0
        self.zd_status = None
        resp = self.send_action("status")
        if not resp:
            return resp
        m = re.search("(?m)^application=(\d+)$", resp)
        if not m:
            return resp
        self.zd_up = 1
        self.zd_pid = int(m.group(1))
        self.zd_status = resp
        m = re.search("(?m)^testing=(\d+)$", resp)
        if m:
            self.zd_testing = int(m.group(1))
        else:
            self.zd_testing = 0

        return resp

    def awhile(self, cond, msg):
        n = 0
        was_running = False
        try:
            if self.get_status():
                was_running = True

            while not cond(n):
                sys.stdout.write(". ")
                sys.stdout.flush()
                time.sleep(1)
                n += 1
                if self.get_status():
                    was_running = True
                elif (was_running or n > 10) and not cond(n):
                    print "\ndaemon manager not running"
                    return

        except KeyboardInterrupt:
            print "^C"
        print "\n" + msg % self.__dict__


    def help_help(self):
        print "help          -- Print a list of available actions."
        print "help <action> -- Print help for <action>."

    def _start_cond(self, n):
        if (n > self.options.start_timeout):
            print '\nProgram took too long to start'
            sys.exit(1)
        return self.zd_pid and not self.zd_testing

    def do_start(self, arg):
        self.get_status()
        if not self.zd_up:
            if self.options.zdrun:
                args = [self.options.python, self.options.zdrun]
            else:
                args = [self.options.python, sys.argv[0]]
                os.environ['DAEMON_MANAGER_MODE'] = '1'

            args += self._get_override("-S", "schemafile")
            args += self._get_override("-C", "configfile")
            args += self._get_override("-b", "backofflimit")
            args += self._get_override("-f", "forever", flag=1)
            args += self._get_override("-s", "sockname")
            args += self._get_override("-u", "user")
            if self.options.umask:
                args += self._get_override("-m", "umask",
                                           oct(self.options.umask))
            args += self._get_override(
                "-x", "exitcodes", ",".join(map(str, self.options.exitcodes)))
            args += self._get_override("-z", "directory")
            args.extend(self.options.program)
            args.extend(self.options.args[1:])
            if self.options.daemon:
                flag = os.P_NOWAIT
            else:
                flag = os.P_WAIT
            os.spawnvp(flag, args[0], args)
        elif not self.zd_pid:
            self.send_action("start")
        else:
            print "daemon process already running; pid=%d" % self.zd_pid
            return
        if self.options.daemon:
            self.awhile(self._start_cond,
                        "daemon process started, pid=%(zd_pid)d",
                        )

    def _get_override(self, opt, name, svalue=None, flag=0):
        value = getattr(self.options, name)
        if value is None:
            return []
        configroot = self.options.configroot
        if configroot is not None:
            for n, cn in self.options.names_list:
                if n == name and cn:
                    v = configroot
                    for p in cn.split("."):
                        v = getattr(v, p, None)
                        if v is None:
                            break
                    if v == value: # We didn't override anything
                        return []
                    break
        if flag:
            if value:
                args = [opt]
            else:
                args = []
        else:
            if svalue is None:
                svalue = str(value)
            args = [opt, svalue]
        return args

    def help_start(self):
        print "start -- Start the daemon process."
        print "         If it is already running, do nothing."

    def do_stop(self, arg):
        self.get_status()
        if not self.zd_up:
            print "daemon manager not running"
        elif not self.zd_pid:
            print "daemon process not running"
        else:
            self.send_action("stop")
            self.awhile(lambda n: not self.zd_pid, "daemon process stopped")

    def do_reopen_transcript(self, arg):
        if not self.zd_up:
            print "daemon manager not running"
        elif not self.zd_pid:
            print "daemon process not running"
        else:
            self.send_action("reopen_transcript")

    def help_stop(self):
        print "stop -- Stop the daemon process."
        print "        If it is not running, do nothing."

    def do_restart(self, arg):
        self.get_status()
        pid = self.zd_pid
        if not pid:
            self.do_start(arg)
        else:
            self.send_action("restart")
            self.awhile(lambda n: (self.zd_pid != pid) and self._start_cond(n),
                        "daemon process restarted, pid=%(zd_pid)d")

    def help_restart(self):
        print "restart -- Stop and then start the daemon process."

    def do_kill(self, arg):
        if not arg:
            sig = signal.SIGTERM
        else:
            try:
                sig = int(arg)
            except: # int() can raise any number of exceptions
                print "invalid signal number", `arg`
                return
        self.get_status()
        if not self.zd_pid:
            print "daemon process not running"
            return
        print "kill(%d, %d)" % (self.zd_pid, sig)
        try:
            os.kill(self.zd_pid, sig)
        except os.error, msg:
            print "Error:", msg
        else:
            print "signal %d sent to process %d" % (sig, self.zd_pid)

    def help_kill(self):
        print "kill [sig] -- Send signal sig to the daemon process."
        print "              The default signal is SIGTERM."

    def do_wait(self, arg):
        self.awhile(lambda n: not self.zd_pid, "daemon process stopped")
        self.do_status()

    def help_wait(self):
        print "wait -- Wait for the daemon process to exit."

    def do_status(self, arg=""):
        if arg not in ["", "-l"]:
            print "status argument must be absent or -l"
            return
        self.get_status()
        if not self.zd_up:
            print "daemon manager not running"
        elif not self.zd_pid:
            print "daemon manager running; daemon process not running"
        else:
            print "program running; pid=%d" % self.zd_pid
        if arg == "-l" and self.zd_status:
            print self.zd_status

    def help_status(self):
        print "status [-l] -- Print status for the daemon process."
        print "               With -l, show raw status output as well."

    def do_show(self, arg):
        if not arg:
            arg = "options"
        try:
            method = getattr(self, "show_" + arg)
        except AttributeError, err:
            print err
            self.help_show()
            return
        method()

    def show_options(self):
        print "zdctl/zdrun options:"
        print "schemafile:  ", repr(self.options.schemafile)
        print "configfile:  ", repr(self.options.configfile)
        print "zdrun:       ", repr(self.options.zdrun)
        print "python:      ", repr(self.options.python)
        print "program:     ", repr(self.options.program)
        print "backofflimit:", repr(self.options.backofflimit)
        print "daemon:      ", repr(self.options.daemon)
        print "forever:     ", repr(self.options.forever)
        print "sockname:    ", repr(self.options.sockname)
        print "exitcodes:   ", repr(self.options.exitcodes)
        print "user:        ", repr(self.options.user)
        umask = self.options.umask
        if not umask:
            # Here we're just getting the current umask so we can report it:
            umask = os.umask(0777)
            os.umask(umask)
        print "umask:       ", oct(umask)
        print "directory:   ", repr(self.options.directory)
        print "logfile:     ", repr(self.options.logfile)

    def show_python(self):
        print "Python info:"
        version = sys.version.replace("\n", "\n              ")
        print "Version:     ", version
        print "Platform:    ", sys.platform
        print "Executable:  ", repr(sys.executable)
        print "Arguments:   ", repr(sys.argv)
        print "Directory:   ", repr(os.getcwd())
        print "Path:"
        for dir in sys.path:
            print "    " + repr(dir)

    def show_all(self):
        self.show_options()
        print
        self.show_python()

    def help_show(self):
        print "show options -- show zdctl options"
        print "show python -- show Python version and details"
        print "show all -- show all of the above"

    def do_logtail(self, arg):
        if not arg:
            arg = self.options.logfile
            if not arg:
                print "No default log file specified; use logtail <logfile>"
                return
        try:
            helper = TailHelper(arg)
            helper.tailf()
        except KeyboardInterrupt:
            print
        except IOError, msg:
            print msg
        except OSError, msg:
            print msg

    def help_logtail(self):
        print "logtail [logfile] -- Run tail -f on the given logfile."
        print "                     A default file may exist."
        print "                     Hit ^C to exit this mode."

    def do_foreground(self, arg):
        self.get_status()
        pid = self.zd_pid
        if pid:
            print "To run the program in the foreground, please stop it first."
            return

        program = self.options.program + self.options.args[1:]
        print " ".join(program)
        sys.stdout.flush()
        try:
            os.spawnlp(os.P_WAIT, program[0], *program)
        except KeyboardInterrupt:
            print

    def do_fg(self, arg):
        self.do_foreground(arg)

    def help_foreground(self):
        print "foreground -- Run the program in the forground."
        print "fg -- an alias for foreground."

    def help_fg(self):
        self.help_foreground()


class TailHelper:

    MAX_BUFFSIZE = 1024

    def __init__(self, fname):
        self.f = open(fname, 'r')

    def tailf(self):
        sz, lines = self.tail(10)
        for line in lines:
            sys.stdout.write(line)
            sys.stdout.flush()
        while 1:
            newsz = self.fsize()
            bytes_added = newsz - sz
            if bytes_added < 0:
                sz = 0
                print "==> File truncated <=="
                bytes_added = newsz
            if bytes_added > 0:
                self.f.seek(-bytes_added, 2)
                bytes = self.f.read(bytes_added)
                sys.stdout.write(bytes)
                sys.stdout.flush()
                sz = newsz
            time.sleep(1)

    def tail(self, max=10):
        self.f.seek(0, 2)
        pos = sz = self.f.tell()

        lines = []
        bytes = []
        num_bytes = 0

        while 1:
            if pos == 0:
                break
            self.f.seek(pos)
            byte = self.f.read(1)
            if byte == '\n':
                if len(lines) == max:
                    break
                bytes.reverse()
                line = ''.join(bytes)
                line and lines.append(line)
                bytes = []
            bytes.append(byte)
            num_bytes = num_bytes + 1
            if num_bytes > self.MAX_BUFFSIZE:
                break
            pos = pos - 1
        lines.reverse()
        return sz, lines

    def fsize(self):
        return os.fstat(self.f.fileno())[stat.ST_SIZE]

def main(args=None, options=None, cmdclass=ZDCmd):
    if args is None:
        args = sys.argv[1:]

    if os.environ.get('DAEMON_MANAGER_MODE'):
        import zdaemon.zdrun
        return zdaemon.zdrun.main(args)

    if options is None:
        options = ZDCtlOptions()
    options.realize(args)
    c = cmdclass(options)
    c.onecmd(" ".join(options.args))

if __name__ == "__main__":
    main()
