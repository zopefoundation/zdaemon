"""Test suite for zdaemon.py (the program)."""

import os
import sys
import time
import signal
import tempfile
import unittest
from StringIO import StringIO

from zdaemon.zdaemon import Daemonizer

class ZDaemonTests(unittest.TestCase):

    python = os.path.abspath(sys.executable)
    assert os.path.exists(python)
    here = os.path.abspath(os.path.dirname(__file__))
    assert os.path.isdir(here)
    nokill = os.path.join(here, "nokill.py")
    assert os.path.exists(nokill)
    parent = os.path.dirname(here)
    zdaemon = os.path.join(parent, "zdaemon.py")
    assert os.path.exists(zdaemon)

    ppath = os.pathsep.join(sys.path)

    def setUp(self):
        self.zdsock = tempfile.mktemp()
        self.new_stdout = StringIO()
        self.save_stdout = sys.stdout
        sys.stdout = self.new_stdout
        self.expect = ""

    def tearDown(self):
        sys.stdout = self.save_stdout
        for sig in (signal.SIGTERM,
                    signal.SIGHUP,
                    signal.SIGINT,
                    signal.SIGCHLD):
            signal.signal(sig, signal.SIG_DFL)
        try:
            os.unlink(self.zdsock)
        except os.error:
            pass
        output = self.new_stdout.getvalue()
        self.assertEqual(self.expect, output)

    def rundaemon(self, args):
        if type(args) is type([]):
            args = " ".join(args)
        cmd = ("PYTHONPATH=%s %s %s -d -s %s %s" %
               (self.ppath, self.python, self.zdaemon, self.zdsock, args))
        os.system(cmd)
        # When the daemon crashes, the following may help debug it:
        ##os.system("%s %s -s %s %s &" %
        ##          (self.python, self.zdaemon, self.zdsock, args))

    def run(self, args):
        if type(args) is type(""):
            args = args.split()
        d = Daemonizer()
        try:
            d.main(["-s", self.zdsock] + args)
        except SystemExit:
            pass

    def testSystem(self):
        self.rundaemon("echo -n")
        self.expect = ""

    def testInvoke(self):
        self.run("echo -n")
        self.expect = ""

    def testControl(self):
        self.rundaemon("sleep 1000")
        time.sleep(1)
        self.run("-c stop")
        time.sleep(1)
        self.run("-c exit")
        self.expect = "Sent SIGTERM\nExiting now\n"

    def testStop(self):
        self.rundaemon([self.python, self.nokill])
        time.sleep(1)
        self.run("-c stop")
        time.sleep(1)
        self.run("-c exit")
        self.expect = "Sent SIGTERM\nSent SIGTERM; will exit later\n"

def test_suite():
    suite = unittest.TestSuite()
    if os.name == "posix":
        suite.addTest(unittest.makeSuite(ZDaemonTests))
    return suite

if __name__ == '__main__':
    __file__ = sys.argv[0]
    unittest.main(defaultTest='test_suite')
