#! /usr/bin/env python

"""
zdctl -- control an application run by zdaemon.

Usage: python zdctl.py config-file [command [arguments]]
"""

import os
import re
import cmd
import sys
import time
import socket

class ZDCmd(cmd.Cmd):

    prompt = "(zdctl) "

    def __init__(self, options):
        self.options = options
        cmd.Cmd.__init__(self)
        self.zdstatus()

    def zdcommand(self, command):
        """Send a command to the zdaemon server and return the response.

        Return None if the server is not up or any other error happened.
        """
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self.options.sockname)
            sock.send(command + "\n")
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

    def zdstatus(self):
        self.zd_up = 0
        self.zd_pid = 0
        self.zd_status = None
        resp = self.zdcommand("status")
        if not resp:
            return
        m = re.search("(?m)^application=(\d+)$", resp)
        if not m:
            return
        self.zd_up = 1
        self.zd_pid = int(m.group(1))
        self.zd_status = resp

    def do_start(self, arg):
        if not self.zd_up:
            command = [self.options.python,
                       self.options.zdaemon,
                       "-d",
                       "-s", self.options.sockname,
                       self.options.program] + self.options.program_arguments
            print command
            os.spawnvp(os.P_WAIT, command[0], command)
        else:
            self.zdcommand("start")
        self.zdstatus()
        while not self.zd_pid:
            sys.stdout.write(". ")
            sys.stdout.flush()
            time.sleep(1)
            self.zdstatus()
        print "started, pid=%d" % self.zd_pid

    def do_stop(self, arg):
        self.zdstatus()
        if not self.zd_up:
            print "daemon manager not running"
        elif not self.zd_pid:
            print "daemon not running"
        else:
            self.zdcommand("stop")
            self.zdstatus()
            while self.zd_pid:
                sys.stdout.write(". ")
                sys.stdout.flush()
                time.sleep(1)
                self.zdstatus()
            print "daemon stopped"

    def do_restart(self, arg):
        self.zdstatus()
        pid = self.zd_pid
        if not pid:
            self.do_start(arg)
        else:
            self.zdcommand("restart")
            self.zdstatus()
            while self.zd_pid in (0, pid):
                sys.stdout.write(". ")
                sys.stdout.flush()
                time.sleep(1)
                self.zdstatus()
            print "daemon restarted, pid=%d" % self.zd_pid

    def do_status(self, arg):
        self.zdstatus()
        if not self.zd_up:
            print "daemon manager not running"
        elif not self.zd_pid:
            print "daemon not running"
        else:
            print "daemon running: pid=%d" % self.zd_pid

    def do_quit(self, arg):
        self.zdstatus()
        if not self.zd_pid:
            self.zdcommand("exit")
            self.zdstatus()
            while self.zd_up:
                sys.stdout.write(". ")
                sys.stdout.flush()
                time.sleep(1)
                self.zdstatus()
            print "daemon not running; daemon manager stopped"
        else:
            print "daemon and daemon manager still running"
        return 1

class ZDOptions:

    python = sys.executable
    if __name__ == "__main__":
        _file = __file__
    else:
        _file = sys.argv[0]
    _file = os.path.normpath(os.path.abspath(_file))
    _dir = os.path.dirname(_file)
    zdaemon = os.path.join(_dir, "zdaemon.py")

    backofflimit = 10                   # -b SECONDS
    isclient = 0                        # -c
    daemon = 0                          # -d
    forever = 0                         # -f
    sockname = "zdsock"                 # -s SOCKET
    exitcodes = [0, 2]                  # -x LIST
    user = None                         # -u USER
    zdirectory = "/"                    # -z DIRECTORY

    program = "sleep"
    program_arguments = ["100"]

##    program = os.path.join(_dir, "tests/nokill.py")
##    program_arguments = []

    def __init__(self, args=None):
        if args is None:
            args = sys.argv[1:]
        self.args = args

def main(args=None):
    options = ZDOptions(args)
    c = ZDCmd(options)
    if options.args:
        c.onecmd(" ".join(options.args))
    else:
        c.cmdloop()

if __name__ == "__main__":
    main()
