"""Test suite for zdrun.py."""

import os
import sys
import time
import signal
import tempfile
import unittest
from StringIO import StringIO

from zdaemon import zdrun

class ZDaemonTests(unittest.TestCase):

    python = os.path.abspath(sys.executable)
    assert os.path.exists(python)
    here = os.path.abspath(os.path.dirname(__file__))
    assert os.path.isdir(here)
    nokill = os.path.join(here, "nokill.py")
    assert os.path.exists(nokill)
    parent = os.path.dirname(here)
    zdrun = os.path.join(parent, "zdrun.py")
    assert os.path.exists(zdrun)

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

    def quoteargs(self, args):
        for i in range(len(args)):
            if " " in args[i]:
                args[i] = '"%s"' % args[i]
        return " ".join(args)

    def rundaemon(self, args):
        # Add quotes, in case some pathname contains spaces (e.g. Mac OS X)
        args = self.quoteargs(args)
        cmd = ('PYTHONPATH="%s" "%s" "%s" -d -s "%s" %s' %
               (self.ppath, self.python, self.zdrun, self.zdsock, args))
        os.system(cmd)
        # When the daemon crashes, the following may help debug it:
        ##os.system("PYTHONPATH=%s %s %s -s %s %s &" %
        ##    (self.ppath, self.python, self.zdrun, self.zdsock, args))

    def run(self, args):
        if type(args) is type(""):
            args = args.split()
        d = zdrun.Daemonizer()
        try:
            d.main(["-s", self.zdsock] + args)
        except SystemExit:
            pass

    def testSystem(self):
        self.rundaemon(["echo", "-n"])
        self.expect = ""

    def testInvoke(self):
        self.run("echo -n")
        self.expect = ""

    def testControl(self):
        self.rundaemon(["sleep", "1000"])
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

    def testHelp(self):
        self.run("-h")
        import __main__
        self.expect = __main__.__doc__

    def testOptionsSysArgv(self):
        # Check that options are parsed from sys.argv by default
        options = zdrun.ZDRunOptions()
        save_sys_argv = sys.argv
        try:
            sys.argv = ["A", "-c", "B", "C"]
            options.realize()
        finally:
            sys.argv = save_sys_argv
        self.assertEqual(options.options, [("-c", "")])
        self.assertEqual(options.isclient, 1)
        self.assertEqual(options.args, ["B", "C"])

    def testOptionsBasic(self):
        # Check basic option parsing
        options = zdrun.ZDRunOptions()
        options.realize(["-c", "B", "C"], "foo")
        self.assertEqual(options.options, [("-c", "")])
        self.assertEqual(options.isclient, 1)
        self.assertEqual(options.args, ["B", "C"])
        self.assertEqual(options.progname, "foo")

    def testOptionsHelp(self):
        # Check that -h behaves properly
        options = zdrun.ZDRunOptions()
        try:
            options.realize(["-h"], doc=zdrun.__doc__)
        except SystemExit, err:
            self.failIf(err.code)
        else:
            self.fail("SystemExit expected")
        self.expect = zdrun.__doc__

    def testSubprocessBasic(self):
        # Check basic subprocess management: spawn, kill, wait
        options = zdrun.ZDRunOptions()
        options.realize([])
        proc = zdrun.Subprocess(options, ["sleep", "100"])
        self.assertEqual(proc.pid, 0)
        pid = proc.spawn()
        self.assertEqual(proc.pid, pid)
        msg = proc.kill(signal.SIGTERM)
        self.assertEqual(msg, None)
        wpid, wsts = os.waitpid(pid, 0)
        self.assertEqual(wpid, pid)
        self.assertEqual(os.WIFSIGNALED(wsts), 1)
        self.assertEqual(os.WTERMSIG(wsts), signal.SIGTERM)
        proc.setstatus(wsts)
        self.assertEqual(proc.pid, 0)

def test_suite():
    suite = unittest.TestSuite()
    if os.name == "posix":
        suite.addTest(unittest.makeSuite(ZDaemonTests))
    return suite

if __name__ == '__main__':
    __file__ = sys.argv[0]
    unittest.main(defaultTest='test_suite')
