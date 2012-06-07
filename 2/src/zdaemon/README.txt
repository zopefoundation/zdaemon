===============
 Using zdaemon
===============

zdaemon provides a script, zdaemon, that can be used to running other
programs as POSIX (Unix) daemons. (Of course, it is only usable on
POSIX-complient systems.

Using zdaemon requires specifying a number of options, which can be
given in a configuration file, or as command-line options.  It also
accepts commands teling it what do do.  The commands are:

start
    Start a process as a daemon

stop
    Stop a running daemon process

restart
    Stop and then restart a program

status
    Find out if the program is running

foreground or fg
    Run a program

kill signal
    Send a signal to the daemon process

reopen_transcript
    Reopen the transcript log.  See the discussion of the transcript
    log below.

help command
    Get help on a command


Commands can be given on a command line, or can be given using an
interactive interpreter.

Let's start with a simple example.  We'll use command-line options to
run the echo command:

    >>> system("./zdaemon -p 'echo hello world' fg")
    echo hello world
    hello world

Here we used the -p option to specify a program to run.  We can
specify a program name and command-line options in the program
command. Note, however, that the command-line parsing is pretty
primitive.  Quotes and spaces aren't handled correctly.  Let's look at
a slightly more complex example.  We'll run the sleep command as a
daemon :)

    >>> system("./zdaemon -p 'sleep 100' start")
    . .
    daemon process started, pid=819

This ran the sleep deamon.  We can check whether it ran with the
status command:

    >>> system("./zdaemon -p 'sleep 100' status")
    program running; pid=819

We can stop it with the stop command:

    >>> system("./zdaemon -p 'sleep 100' stop")
    . .
    daemon process stopped

    >>> system("./zdaemon -p 'sleep 100' status")
    daemon manager not running

Normally, we control zdaemon using a configuration file.  Let's create
a typical configuration file:

    >>> open('conf', 'w').write(
    ... '''
    ... <runner>
    ...   program sleep 100
    ... </runner>
    ... ''')

Now, we can run with the -C option to read the configuration file:

    >>> system("./zdaemon -Cconf start")
    . .
    daemon process started, pid=1136

If we list the directory:

    >>> system("ls")
    conf
    zdaemon
    zdsock

We'll see that a file, zdsock, was created.  This is a unix-domain
socket used internally by ZDaemon.  We'll normally want to control
where this goes.

    >>> system("./zdaemon -Cconf stop")
    . .
    daemon process stopped

    >>> open('conf', 'w').write(
    ... '''
    ... <runner>
    ...   program sleep 100
    ...   socket-name /tmp/demo.zdsock
    ... </runner>
    ... '''.replace('/tmp', tmpdir))


    >>> system("./zdaemon -Cconf start")
    . .
    daemon process started, pid=1139

    >>> system("ls")
    conf
    zdaemon

    >>> import os
    >>> os.path.exists("/tmp/demo.zdsock".replace('/tmp', tmpdir))
    True

    >>> system("./zdaemon -Cconf stop")
    . .
    daemon process stopped

In the example, we included a command-line argument in the program
option. We can also provide options on the command line:

    >>> open('conf', 'w').write(
    ... '''
    ... <runner>
    ...   program sleep
    ...   socket-name /tmp/demo.zdsock
    ... </runner>
    ... '''.replace('/tmp', tmpdir))

    >>> system("./zdaemon -Cconf start 100")
    . .
    daemon process started, pid=1149

    >>> system("./zdaemon -Cconf status")
    program running; pid=1149

    >>> system("./zdaemon -Cconf stop")
    . .
    daemon process stopped

Environment Variables
=====================

Sometimes, it is necessary to set environment variables before running
a program.  Perhaps the most common case for this is setting
LD_LIBRARY_PATH so that dynamically loaded libraries can be found.

    >>> open('conf', 'w').write(
    ... '''
    ... <runner>
    ...   program env
    ...   socket-name /tmp/demo.zdsock
    ... </runner>
    ... <environment>
    ...   LD_LIBRARY_PATH /home/foo/lib
    ...   HOME /home/foo
    ... </environment>
    ... '''.replace('/tmp', tmpdir))

    >>> system("./zdaemon -Cconf fg")
    env
    USER=jim
    HOME=/home/foo
    LOGNAME=jim
    USERNAME=jim
    TERM=dumb
    PATH=/home/jim/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin
    EMACS=t
    LANG=en_US.UTF-8
    SHELL=/bin/bash
    EDITOR=emacs
    LD_LIBRARY_PATH=/home/foo/lib

Transcript log
==============

When zdaemon run a program in daemon mode, it disconnects the
program's standard input, standard output, and standard error from the
controlling terminal.  It can optionally redirect the output to
standard error and standard output to a file.  This is done with the
transcript option.  This is, of course, useful for logging output from
long-running applications.

Let's look at an example. We'll have a long-running process that
simple tails a data file:

    >>> f = open('data', 'w', 0)
    >>> import os
    >>> f.write('rec 1\n'); os.fsync(f.fileno())

    >>> open('conf', 'w').write(
    ... '''
    ... <runner>
    ...   program tail -f data
    ...   transcript log
    ... </runner>
    ... ''')

    >>> system("./zdaemon -Cconf start")
    . .
    daemon process started, pid=7963

.. Wait a little bit to make sure tail has a chance to work

    >>> import time
    >>> time.sleep(0.1)

Now, if we look at the log file, it contains the tail output:

    >>> open('log').read()
    'rec 1\n'

We can rotate the transcript log by renaming it and telling zdaemon to
reopen it:

    >>> import os
    >>> os.rename('log', 'log.1')

If we generate more output:

    >>> f.write('rec 2\n'); os.fsync(f.fileno())

.. Wait a little bit to make sure tail has a chance to work

    >>> time.sleep(1)

The output will appear in the old file, because zdaemon still has it
open:

    >>> open('log.1').read()
    'rec 1\nrec 2\n'

Now, if we tell zdaemon to reopen the file:

    >>> system("./zdaemon -Cconf reopen_transcript")

and generate some output:

    >>> f.write('rec 3\n'); os.fsync(f.fileno())

.. Wait a little bit to make sure tail has a chance to work

    >>> time.sleep(1)

the output will show up in the new file, not the old:

    >>> open('log').read()
    'rec 3\n'

    >>> open('log.1').read()
    'rec 1\nrec 2\n'

Reference Documentation
=======================

The following options are available for use in the runner section of
configuration files and as command-line options.

program
        Command-line option: -p or --program

        This option gives the command used to start the subprocess
        managed by zdaemon.  This is currently a simple list of
        whitespace-delimited words. The first word is the program
        file, subsequent words are its command line arguments.  If the
        program file contains no slashes, it is searched using $PATH.
        (Note that there is no way to to include whitespace in the program
        file or an argument, and under certain circumstances other
        shell metacharacters are also a problem.)

socket-name
        Command-line option: -s or --socket-name.

        The pathname of the Unix domain socket used for communication
        between the zdaemon command-line tool and a deamon-management
        process.  The default is relative to the current directory in
        which zdaemon is started.  You want to specify
        an absolute pathname here.

        This defaults to "zdsock", which is created in the directory
        in which zdrun is started.

daemon
        Command-line option: -d or --daemon.

        If this option is true, zdaemon runs in the background as a
        true daemon.  It forks a child process which becomes the
        subprocess manager, while the parent exits (making the shell
        that started it believe it is done).  The child process also
        does the following:

        - if the directory option is set, change into that directory

        - redirect stdin, stdout and stderr to /dev/null

        - call setsid() so it becomes a session leader

        - call umask() with specified value

        The default for this option is on by default.  The
        command-line option therefore has no effect.  To disable
        daemon mode, you must use a configuration file::

          <runner>
            program sleep 1
            daemon off
          </runner>

directory
        Command-line option: -z or --directory.

        If the daemon option is true (default), this option can
        specify a directory into which zdrun.py changes as part of the
        "daemonizing".  If the daemon option is false, this option is
        ignored.

backoff-limit
        Command-line option: -b or --backoff-limit.

        When the subprocess crashes, zdaemon inserts a one-second
        delay before it restarts it.  When the subprocess crashes
        again right away, the delay is incremented by one second, and
        so on.  What happens when the delay has reached the value of
        backoff-limit (in seconds), depends on the value of the
        forever option.  If forever is false, zdaemon gives up at
        this point, and exits.  An always-crashing subprocess will
        have been restarted exactly backoff-limit times in this case.
        If forever is true, zdaemon continues to attempt to restart
        the process, keeping the delay at backoff-limit seconds.

        If the subprocess stays up for more than backoff-limit
        seconds, the delay is reset to 1 second.

        This defaults to 10.

forever
        Command-line option: -f or --forever.

        If this option is true, zdaemon will keep restarting a
        crashing subprocess forever.  If it is false, it will give up
        after backoff-limit crashes in a row.  See the description of
        backoff-limit for details.

        This is disabled by default.

exit-codes
        Command-line option: -x or --exit-codes.

        This defaults to 0,2.

        If the subprocess exits with an exit status that is equal to
        one of the integers in this list, zdaemon will not restart
        it.  The default list requires some explanation.  Exit status
        0 is considered a willful successful exit; the ZEO and Zope
        server processes use this exit status when they want to stop
        without being restarted.  (Including in response to a
        SIGTERM.)  Exit status 2 is typically issued for command line
        syntax errors; in this case, restarting the program will not
        help!

        NOTE: this mechanism overrides the backoff-limit and forever
        options; i.e. even if forever is true, a subprocess exit
        status code in this list makes zdaemon give up.  To disable
        this, change the value to an empty list.

user
        Command-line option: -u or --user.

        When zdaemon is started by root, this option specifies the
        user as who the the zdaemon process (and hence the daemon
        subprocess) will run.  This can be a user name or a numeric
        user id.  Both the user and the group are set from the
        corresponding password entry, using setuid() and setgid().
        This is done before zdaemon does anything else besides
        parsing its command line arguments.

        NOTE: when zdaemon is not started by root, specifying this
        option is an error.  (XXX This may be a mistake.)

        XXX The zdaemon event log file may be opened *before*
        setuid() is called.  Is this good or bad?

umask
        Command-line option: -m or --umask.

        When daemon mode is used, this option specifies the octal umask
        of the subprocess.

default-to-interactive
        If this option is true, zdaemon enters interactive mode
        when it is invoked without a positional command argument.  If
        it is false, you must use the -i or --interactive command line
        option to zdaemon to enter interactive mode.

        This is enabled by default.

logfile
        This option specifies a log file that is the default target of
        the "logtail" zdaemon command.

        NOTE: This is NOT the log file to which zdaemon writes its
        logging messages!  That log file is specified by the
        <eventlog> section described below.

transcript
        The name of a file in which a transcript of all output from
        the command being run will be written to when daemonized.

        If not specified, output from the command will be discarded.

        This only takes effect when the "daemon" option is enabled.

prompt
         The prompt shown by the controller program.  The default must
         be provided by the application.

(Note that a few other options are available to support old
configuration files, but aren't needed any more and can generally be
ignored.)

In addition to the runner section, you can use an eventlog section
that specified one or more logfile subsections::

    <eventlog>
      <logfile>
        path /var/log/foo/foo.log
      </logfile>

      <logfile>
        path STDOUT
      </logfile>
    </eventlog>

In this example, log output is sent to a file and to standard out.
Log output from zdaemon usually isn't very interesting but can be
handy for debugging.
