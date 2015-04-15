"""Test suite for zdctl.py."""

import doctest

from zdaemon import zdctl


def run(args):
    options = zdctl.ZDCtlOptions()
    options.realize(['-p', 'true'] + args.split())
    cmd = zdctl.ZDCmd(options)
    cmd.onecmd(" ".join(options.args))


def doctest_ZDCmd_help():
    """Test for ZDCmd.help_xxx

        >>> run("help")
        <BLANKLINE>
        Documented commands (type help <topic>):
        ========================================
        fg          help  logreopen  reopen_transcript  show   status  wait
        foreground  kill  logtail    restart            start  stop
        <BLANKLINE>

        >>> run("help fg")
        foreground -- Run the program in the forground.
        fg -- an alias for foreground.

        >>> run("help help")
        help          -- Print a list of available actions.
        help <action> -- Print help for <action>.

        >>> run("help kill")
        kill [sig] -- Send signal sig to the daemon process.
                      The default signal is SIGTERM.

        >>> run("help logreopen")
        logreopen -- Send a SIGUSR2 signal to the daemon process.
                     This is designed to reopen the log file.
                     Also reopens the transcript log file.

        >>> run("help logtail")
        logtail [logfile] -- Run tail -f on the given logfile.
                             A default file may exist.
                             Hit ^C to exit this mode.

        >>> run("help reopen_transcript")
        reopen_transcript -- Reopen the transcript log file.
                             Use after log rotation.

        >>> run("help restart")
        restart -- Stop and then start the daemon process.

        >>> run("help show")
        show options -- show zdctl options
        show python -- show Python version and details
        show all -- show all of the above

        >>> run("help start")
        start -- Start the daemon process.
                 If it is already running, do nothing.

        >>> run("help status")
        status [-l] -- Print status for the daemon process.
                       With -l, show raw status output as well.

        >>> run("help stop")
        stop -- Stop the daemon process.
                If it is not running, do nothing.

        >>> run("help wait")
        wait -- Wait for the daemon process to exit.

    """


def test_suite():
    return doctest.DocTestSuite(optionflags=doctest.NORMALIZE_WHITESPACE)
