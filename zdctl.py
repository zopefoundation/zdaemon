#! /usr/bin/env python
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

Usage: python zdctl.py -C config-file [action [arguments]]

Options:
-C/--configuration URL -- configuration file or URL
action [arguments] -- see below

If no action is specified on the command line, a "shell" interpreting
actions typed interactively is started.

Use the action "help" to find out about available actions.
"""

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

from ZEO.runsvr import Options


class ZDOptions(Options):

    # Where's python?
    python = sys.executable

    # Where's zdaemon?
    if __name__ == "__main__":
        _file = sys.argv[0]
    else:
        _file = __file__
    _file = os.path.normpath(os.path.abspath(_file))
    _dir = os.path.dirname(_file)
    zdaemon = os.path.join(_dir, "zdaemon.py")

    # Options for zdaemon
    backofflimit = 10                   # -b SECONDS
    forever = 0                         # -f
    sockname = os.path.abspath("zdsock") # -s SOCKET
    exitcodes = [0, 2]                  # -x LIST
    user = None                         # -u USER
    zdirectory = "/"                    # -z DIRECTORY

    # Program (and arguments) for zdaemon
    program = None

    def load_configuration(self):
        Options.load_configuration(self) # Sets self.rootconf
        if not self.rootconf:
            self.usage("a configuration file is required; use -C")
        # XXX Should allow overriding more zdaemon options here
        if self.program is None:
            self.program = self.rootconf.getlist("program")
        if self.program is None:
            self.usage("no program specified in configuration")


class ZDCmd(cmd.Cmd):

    prompt = "(zdctl) "

    def __init__(self, options):
        print "program:", " ".join(options.program)
        self.options = options
        cmd.Cmd.__init__(self)
        self.do_status()
        if self.zd_status:
            m = re.search("(?m)^args=(.*)$", self.zd_status)
            if m:
                s = m.group(1)
                args = eval(s, {"__builtins__": {}})
                if args != self.options.program:
                    print "WARNING! zdaemon is managing a different program!"
                    print "our program   =", self.options.program
                    print "daemon's args =", args

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
            print "response =", `response`
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

    def do_start(self, arg):
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
            print args
            os.spawnvp(os.P_WAIT, args[0], args)
        else:
            self.send_action("start")
        self.awhile(lambda: self.zd_pid, "started, pid=%(zd_pid)d")

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

    def do_quit(self, arg):
        self.get_status()
        if not self.zd_pid:
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
    options = ZDOptions(args)
    c = ZDCmd(options)
    if options.args:
        c.onecmd(" ".join(options.args))
    else:
        c.cmdloop()

if __name__ == "__main__":
    main()
