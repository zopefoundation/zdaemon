Using zdaemon
=============

zdaemon provides a script, zdaemon, that can be used to running other
programs as POSIX (Unix) daemons. (Of course, it is only usable on
POSIX-complient systems.

Using zdaemon requires specifying a number of options, which can be
given in a configuration file, or as command-line options.  It also
accepts commands teling it what do do.  The commants are:

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
    . daemon process started, pid=819

This ran the sleep deamon.  We can check whether it ran with the
status command:  

    >>> system("./zdaemon -p 'sleep 100' status")
    program running; pid=819

We can stop it with the stop command:

    >>> system("./zdaemon -p 'sleep 100' stop")
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
    . daemon process started, pid=1136

If we list the directory:

    >>> system("ls")
    conf
    zdaemon
    zdsock

We'll see that a file, zdsock, was created.  This is a unix-domain
socket used internally by ZDaemon.  We'll normally want to control
where this goes.

    >>> system("./zdaemon -Cconf stop")
    daemon process stopped

    >>> open('conf', 'w').write(
    ... '''
    ... <runner>
    ...   program sleep 100
    ...   socket-name /tmp/demo.zdsock
    ... </runner>
    ... ''')


    >>> system("./zdaemon -Cconf start")
    . daemon process started, pid=1139

    >>> system("ls")
    conf
    zdaemon

    >>> import os
    >>> os.path.exists("/tmp/demo.zdsock")
    True

    >>> system("./zdaemon -Cconf stop")
    daemon process stopped

In the example, we included a command-line argument in the program
option. We can also provide options on the command line:

    >>> open('conf', 'w').write(
    ... '''
    ... <runner>
    ...   program sleep
    ...   socket-name /tmp/demo.zdsock
    ... </runner>
    ... ''')

    >>> system("./zdaemon -Cconf start 100")
    . daemon process started, pid=1149

    >>> system("./zdaemon -Cconf status")
    program running; pid=1149

    >>> system("./zdaemon -Cconf stop")
    daemon process stopped

