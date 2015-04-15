"""Test suite for zdrun.py."""
from __future__ import print_function

import os
import sys
import time
import shutil
import signal
import tempfile
import unittest
import socket

try:
    from StringIO import StringIO
except:
    # Python 3 support.
    from io import StringIO

import ZConfig

from zdaemon import zdrun, zdctl


class ConfiguredOptions:
    """Options class that loads configuration from a specified string.

    This always loads from the string, regardless of any -C option
    that may be given.
    """

    def set_configuration(self, configuration):
        self.__configuration = configuration
        self.configfile = "<preloaded string>"

    def load_configfile(self):
        sio = StringIO(self.__configuration)
        cfg = ZConfig.loadConfigFile(self.schema, sio, self.zconfig_options)
        self.configroot, self.confighandlers = cfg


class ConfiguredZDRunOptions(ConfiguredOptions, zdrun.ZDRunOptions):

    def __init__(self, configuration):
        zdrun.ZDRunOptions.__init__(self)
        self.set_configuration(configuration)


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
        #   os.system("PYTHONPATH=%s %s %s -s %s %s &" %
        #       (self.ppath, self.python, self.zdrun, self.zdsock, args))

    def _run(self, args, cmdclass=None, module=zdctl):
        if isinstance(args, str):
            args = args.split()
        kw = {}
        if cmdclass:
            kw['cmdclass'] = cmdclass
        try:
            module.main(["-s", self.zdsock] + args, **kw)
        except SystemExit:
            pass

    def testCmdclassOverride(self):
        class MyCmd(zdctl.ZDCmd):
            def do_sproing(self, rest):
                print(rest)
        self._run("-p echo sproing expected", cmdclass=MyCmd)
        self.expect = "expected\n"

    def testSystem(self):
        self.rundaemon(["echo", "-n"])
        self.expect = ""

    def test_help_zdrun(self):
        self._run("-h", module=zdrun)
        self.expect = zdrun.__doc__

    def test_help_zdctl(self):
        self._run("-h")
        self.expect = zdctl.__doc__

    def testOptionsSysArgv(self):
        # Check that options are parsed from sys.argv by default
        options = zdrun.ZDRunOptions()
        save_sys_argv = sys.argv
        try:
            sys.argv = ["A", "B", "C"]
            options.realize()
        finally:
            sys.argv = save_sys_argv
        self.assertEqual(options.options, [])
        self.assertEqual(options.args, ["B", "C"])

    def testOptionsBasic(self):
        # Check basic option parsing
        options = zdrun.ZDRunOptions()
        options.realize(["B", "C"], "foo")
        self.assertEqual(options.options, [])
        self.assertEqual(options.args, ["B", "C"])
        self.assertEqual(options.progname, "foo")

    def testOptionsHelp(self):
        # Check that -h behaves properly
        options = zdrun.ZDRunOptions()
        try:
            options.realize(["-h"], doc=zdrun.__doc__)
        except SystemExit as err:
            self.assertEqual(err.code, 0)
        else:
            self.fail("SystemExit expected")
        self.expect = zdrun.__doc__

    def testSubprocessBasic(self):
        # Check basic subprocess management: spawn, kill, wait
        options = zdrun.ZDRunOptions()
        options.realize(["sleep", "100"])
        proc = zdrun.Subprocess(options)
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

    def testEventlogOverride(self):
        # Make sure runner.eventlog is used if it exists
        options = ConfiguredZDRunOptions("""\
            <runner>
              program /bin/true
              <eventlog>
                level 42
              </eventlog>
            </runner>

            <eventlog>
              level 35
            </eventlog>
            """)
        options.realize(["/bin/true"])
        self.assertEqual(options.config_logger.level, 42)

    def testEventlogWithoutOverride(self):
        # Make sure eventlog is used if runner.eventlog doesn't exist
        options = ConfiguredZDRunOptions("""\
            <runner>
              program /bin/true
            </runner>

            <eventlog>
              level 35
            </eventlog>
            """)
        options.realize(["/bin/true"])
        self.assertEqual(options.config_logger.level, 35)

    def testRunIgnoresParentSignals(self):
        # Spawn a process which will in turn spawn a zdrun process.
        # We make sure that the zdrun process is still running even if
        # its parent process receives an interrupt signal (it should
        # not be passed to zdrun).
        tmp = tempfile.mkdtemp()
        zdrun_socket = os.path.join(tmp, 'testsock')
        try:
            zdctlpid = os.spawnvpe(
                os.P_NOWAIT,
                sys.executable,
                [sys.executable, os.path.join(self.here, 'parent.py'), tmp],
                dict(os.environ,
                     PYTHONPATH=":".join(sys.path),
                     )
            )
            # Wait for it to start, but no longer than a minute.
            deadline = time.time() + 60
            is_started = False
            while time.time() < deadline:
                response = send_action('status\n', zdrun_socket)
                if response is None:
                    time.sleep(0.05)
                else:
                    is_started = True
                    break
            self.assertTrue(is_started,
                            "spawned process failed to start in a minute")
            # Kill it, and wait a little to ensure it's dead.
            os.kill(zdctlpid, signal.SIGINT)
            time.sleep(0.25)
            # Make sure the child is still responsive.
            response = send_action('status\n', zdrun_socket,
                                   raise_on_error=True)
            self.assertTrue(b'\n' in response,
                            'no newline in response: ' + repr(response))
            # Kill the process.
            send_action('stop\n', zdrun_socket)
        finally:
            # Remove the tmp directory.
            # Caution:  this is delicate.  The code here used to do
            # shutil.rmtree(tmp), but that suffers a sometimes-fatal
            # race with zdrun.py.  The 'testsock' socket is created
            # by zdrun in the tmp directory, and zdrun tries to
            # unlink it.  If shutil.rmtree sees 'testsock' too, it
            # will also try to unlink it, but zdrun may complete
            # unlinking it before shutil gets to it (there's more
            # than one process here).  So, in effect, we code a
            # 1-level rmtree inline here, suppressing errors.
            for fname in os.listdir(tmp):
                try:
                    os.unlink(os.path.join(tmp, fname))
                except os.error:
                    pass
            os.rmdir(tmp)

    def testUmask(self):
        # people have a strange tendency to run the tests as root
        if os.getuid() == 0:
            self.fail("""
I am root!
Do not run the tests as root.
Testing proper umask handling cannot be done as root.
Furthermore, it is not a good idea and strongly discouraged to run zope, the
build system (configure, make) or the tests as root.
In general do not run anything as root unless absolutely necessary.
""")

        path = tempfile.mktemp()
        # With umask 666, we should create a file that we aren't able
        # to write.  If access says no, assume that umask works.
        try:
            touch_cmd = "/bin/touch"
            if not os.path.exists(touch_cmd):
                touch_cmd = "/usr/bin/touch"  # Mac OS X
            self.rundaemon(["-m", "666", touch_cmd, path])
            for i in range(5):
                if not os.path.exists(path):
                    time.sleep(0.1)
            self.assertTrue(os.path.exists(path))
            self.assertTrue(not os.access(path, os.W_OK))
        finally:
            if os.path.exists(path):
                os.remove(path)


class TestRunnerDirectory(unittest.TestCase):

    def setUp(self):
        super(TestRunnerDirectory, self).setUp()
        self.root = tempfile.mkdtemp()
        self.save_stdout = sys.stdout
        self.save_stderr = sys.stdout
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        self.expect = ''
        self.cmd = "/bin/true"
        if not os.path.exists(self.cmd):
            self.cmd = "/usr/bin/true"  # Mac OS X

    def tearDown(self):
        shutil.rmtree(self.root)
        got = sys.stdout.getvalue()
        err = sys.stderr.getvalue()
        sys.stdout = self.save_stdout
        sys.stderr = self.save_stderr
        if err:
            print(err, end='', file=sys.stderr)
        self.assertEqual(self.expect, got)
        super(TestRunnerDirectory, self).tearDown()

    def run_ctl(self, opts):
        options = zdctl.ZDCtlOptions()
        options.realize(opts + ['fg'])
        self.expect = self.cmd + '\n'
        proc = zdctl.ZDCmd(options)
        proc.onecmd(" ".join(options.args))

    def testCtlRunDirectoryCreation(self):
        path = os.path.join(self.root, 'rundir')
        self.run_ctl(['-z', path, '-p', self.cmd])
        self.assertTrue(os.path.exists(path))

    def testCtlRunDirectoryCreationFromConfigFile(self):
        path = os.path.join(self.root, 'rundir')
        options = ['directory ' + path,
                   'program ' + self.cmd]
        config = self.writeConfig(
            '<runner>\n%s\n</runner>' % '\n'.join(options))
        self.run_ctl(['-C', config])
        self.assertTrue(os.path.exists(path))

    def testCtlRunDirectoryCreationOnlyOne(self):
        path = os.path.join(self.root, 'rundir', 'not-created')
        self.assertRaises(SystemExit,
                          self.run_ctl, ['-z', path, '-p', self.cmd])
        self.assertFalse(os.path.exists(path))
        got = sys.stderr.getvalue().strip()
        sys.stderr = StringIO()
        self.assertTrue(got.startswith('Error: invalid value for -z'))

    def testCtlSocketDirectoryCreation(self):
        path = os.path.join(self.root, 'rundir', 'sock')
        self.run_ctl(['-s', path, '-p', self.cmd])
        self.assertTrue(os.path.exists(os.path.dirname(path)))

    def testCtlSocketDirectoryCreationRelativePath(self):
        path = os.path.join('rundir', 'sock')
        self.run_ctl(['-s', path, '-p', self.cmd])
        self.assertTrue(
            os.path.exists(os.path.dirname(os.path.join(os.getcwd(), path))))

    def testCtlSocketDirectoryCreationOnlyOne(self):
        path = os.path.join(self.root, 'rundir', 'not-created', 'sock')
        self.assertRaises(SystemExit,
                          self.run_ctl, ['-s', path, '-p', self.cmd])
        self.assertFalse(os.path.exists(path))
        got = sys.stderr.getvalue().strip()
        sys.stderr = StringIO()
        self.assertTrue(got.startswith('Error: invalid value for -s'))

    def testCtlSocketDirectoryCreationFromConfigFile(self):
        path = os.path.join(self.root, 'rundir')
        options = ['socket-name %s/sock' % path,
                   'program ' + self.cmd]
        config = self.writeConfig(
            '<runner>\n%s\n</runner>' % '\n'.join(options))
        self.run_ctl(['-C', config])
        self.assertTrue(os.path.exists(path))

    def testCtlSocketDirectoryCreationFromConfigFileRelativePath(self):
        path = 'rel-rundir'
        options = ['socket-name %s/sock' % path,
                   'program ' + self.cmd]
        config = self.writeConfig(
            '<runner>\n%s\n</runner>' % '\n'.join(options))
        self.run_ctl(['-C', config])
        self.assertTrue(os.path.exists(os.path.join(os.getcwd(), path)))

    def writeConfig(self, config):
        config_file = os.path.join(self.root, 'config')
        with open(config_file, 'w') as f:
            f.write(config)
        return config_file

    def testDirectoryChown(self):
        path = os.path.join(self.root, 'foodir')
        options = zdctl.ZDCtlOptions()
        options.realize(['-p', self.cmd, 'status'])
        cmd = zdctl.ZDCmd(options)
        options.uid = 27
        options.gid = 28
        # Patch chown and geteuid, because we're not root
        chown = os.chown
        geteuid = os.geteuid
        calls = []

        def my_chown(*args):
            calls.append(('chown',) + args)

        def my_geteuid():
            return 0

        try:
            os.chown = my_chown
            os.geteuid = my_geteuid
            cmd.create_directory(path)
        finally:
            os.chown = chown
            os.geteuid = geteuid
        self.assertEqual([('chown', path, 27, 28)], calls)


def send_action(action, sockname, raise_on_error=False):
    """Send an action to the zdrun server and return the response.

    Return None if the server is not up or any other error happened.
    """
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(sockname)
        sock.send(action.encode() + b"\n")
        sock.shutdown(1)  # We're not writing any more
        response = b""
        while 1:
            data = sock.recv(1000)
            if not data:
                break
            response += data
        sock.close()
        return response
    except socket.error as msg:
        if str(msg) == 'AF_UNIX path too long':
            # MacOS has apparent small limits on the length of a UNIX
            # domain socket filename, we want to make MacOS users aware
            # of the actual problem
            raise
        if raise_on_error:
            raise
        return None
    finally:
        sock.close()


def test_suite():
    suite = unittest.TestSuite()
    if os.name == "posix":
        suite.addTest(unittest.makeSuite(ZDaemonTests))
        suite.addTest(unittest.makeSuite(TestRunnerDirectory))
    return suite

if __name__ == '__main__':
    __file__ = sys.argv[0]
    unittest.main(defaultTest='test_suite')
