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
"""zdctl -- control an application run by zdaemon.

Usage: python zdctl.py [-C URL] [-h] [-p PROGRAM] [action [arguments]]

Options:
-C/--configuration URL -- configuration file or URL
-h/--help -- print usage message and exit
-p/--program PROGRAM -- the program to run
action [arguments] -- see below

Actions are commands like "start", "stop" and "status".  If no action
is specified on the command line, a "shell" interpreting actions typed
interactively is started.  Use the action "help" to find out about
available actions.
"""

from __future__ import nested_scopes

# XXX Related code lives in lib/python/Zope/Startup/ZctlLib.py on the
# 'chrism-install-branch' branch.
# The code there knows more about Zope and about Windows, but doesn't
# use zdaemon.py or ZConfig.

import os
import re
import cmd
import sys
import time
import signal
import socket

if __name__ == "__main__":
    # Add the parent of the script directory to the module search path
    from os.path import dirname, abspath, normpath
    sys.path.append(dirname(dirname(normpath(abspath(sys.argv[0])))))

import ZConfig
from zdaemon.zdoptions import ZDOptions


def string_list(arg):
    return arg.split()


class ZDCtlOptions(ZDOptions):

    positional_args_allowed = 1

    # Where's python?
    python = sys.executable

    # Where's zdaemon?
    if __name__ == "__main__":
        _file = sys.argv[0]
    else:
        _file = __file__
    _file = os.path.normpath(os.path.abspath(_file))
    _dir = os.path.dirname(_file)
    zdaemon = os.path.join(_dir, "zdrun.py")

    # Options for zdaemon
    backofflimit = 10                   # -b SECONDS
    forever = 0                         # -f
    sockname = os.path.abspath("zdsock") # -s SOCKET
    exitcodes = [0, 2]                  # -x LIST
    user = None                         # -u USER
    zdirectory = "/"                    # -z DIRECTORY

    def __init__(self):
        ZDOptions.__init__(self)
        self.add("program", "zdctl.program", "p:", "program=",
                 handler=string_list,
                 required="no program specified; use -p or -C")


class ZDCmd(cmd.Cmd):

    prompt = "zdctl> "

    def __init__(self, options):
        self.options = options
        cmd.Cmd.__init__(self)
        self.get_status()
        if self.zd_status:
            m = re.search("(?m)^args=(.*)$", self.zd_status)
            if m:
                s = m.group(1)
                args = eval(s, {"__builtins__": {}})
                if args != self.options.program:
                    print "WARNING! zdaemon is managing a different program!"
                    print "our program   =", self.options.program
                    print "daemon's args =", args

    def emptyline(self):
        pass # We don't want a blank line to repeat the last command

    def send_action(self, action):
        """Send an action to the zdaemon server and return the response.

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

    def get_status(self):
        self.zd_up = 0
        self.zd_pid = 0
        self.zd_status = None
        resp = self.send_action("status")
        if not resp:
            return
        m = re.search("(?m)^application=(\d+)$", resp)
        if not m:
            return
        self.zd_up = 1
        self.zd_pid = int(m.group(1))
        self.zd_status = resp

    def awhile(self, cond, msg):
        try:
            self.get_status()
            while not cond():
                sys.stdout.write(". ")
                sys.stdout.flush()
                time.sleep(1)
                self.get_status()
        except KeyboardInterrupt:
            print "^C"
        else:
            print msg % self.__dict__

    def help_help(self):
        print "help          -- Print a list of available actions."
        print "help <action> -- Print help for <action>."

    def do_EOF(self, arg):
        print
        return 1

    def do_start(self, arg):
        self.get_status()
        if not self.zd_up:
            args = [
                self.options.python,
                self.options.zdaemon,
                "-b", str(self.options.backofflimit),
                "-d",
                "-s", self.options.sockname,
                "-x", ",".join(map(str, self.options.exitcodes)),
                "-z", self.options.zdirectory,
                ]
            if self.options.forever:
                args.append("-f")
            if self.options.user:
                argss.extend(["-u", str(self.options.user)])
            args.extend(self.options.program)
            os.spawnvp(os.P_WAIT, args[0], args)
        elif not self.zd_pid:
            self.send_action("start")
        else:
            print "daemon process already running; pid=%d" % self.zd_pid
            return
        self.awhile(lambda: self.zd_pid,
                    "daemon process started, pid=%(zd_pid)d")

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
            self.awhile(lambda: not self.zd_pid, "daemon process stopped")

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
            self.awhile(lambda: self.zd_pid not in (0, pid),
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
        self.awhile(lambda: not self.zd_pid, "daemon process stopped")
        self.do_status()

    def help_wait(self):
        print "wait -- Wait for the daemon process to exit."

    def do_status(self, arg=""):
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
            args = ["options"]
        else:
            args = arg.split()
        methods = []
        for arg in args:
            try:
                method = getattr(self, "show_" + arg)
            except AttributeError:
                self.help_show()
                return
            methods.append(method)
        for method in methods:
            method()

    def show_options(self):
        print "schemafile:  ", repr(self.options.schemafile)
        print "configfile:  ", repr(self.options.configfile)
        print "zdaemon:     ", repr(self.options.zdaemon)
        print "program:     ", repr(self.options.program)
        print "backofflimit:", repr(self.options.backofflimit)
        print "forever:     ", repr(self.options.forever)
        print "sockname:    ", repr(self.options.sockname)
        print "exitcodes:   ", repr(self.options.exitcodes)
        print "user:        ", repr(self.options.user)
        print "zdirectory:  ", repr(self.options.zdirectory)

    def show_python(self):
        version = sys.version.replace("\n", "\n              ")
        print "Version:     ", version
        print "Platform:    ", sys.platform
        print "Executable:  ", repr(sys.executable)
        print "Arguments:   ", repr(sys.argv)
        print "Directory:   ", repr(os.getcwd())
        print "Path:"
        for dir in sys.path:
            print "    " + repr(dir)

    def help_show(self):
        print "show options -- show zdctl options"
        print "show python -- show Python version and details"

    def complete_show(self, text, *ignored):
        options = ["options", "python"]
        return [x for x in options if x.startswith(text)]

    def do_logreopen(self, arg):
        self.do_kill(str(signal.SIGUSR2))

    def help_logreopen(self):
        print "logreopen -- Send a SIGUSR2 signal to the daemon process."
        print "             This is designed to reopen the log file."

    def do_quit(self, arg):
        self.get_status()
        if not self.zd_up:
            print "daemon manager not running"
        elif not self.zd_pid:
            print "daemon process not running; stopping daemon manager"
            self.send_action("exit")
            self.awhile(lambda: not self.zd_up, "daemon manager stopped")
        else:
            print "daemon process and daemon manager still running"
        return 1

    def help_quit(self):
        print "quit -- Exit the zdctl shell."
        print ("        If the daemon process is not running, "
               "stop the daemon manager.")

def main(args=None):
    options = ZDCtlOptions()
    options.realize(args)
    c = ZDCmd(options)
    if options.args:
        c.onecmd(" ".join(options.args))
    else:
        print "program:", " ".join(options.program)
        c.do_status()
        c.cmdloop()

if __name__ == "__main__":
    main()
