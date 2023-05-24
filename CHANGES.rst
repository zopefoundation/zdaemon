==========
Change log
==========

5.0 (2023-05-24)
================

- Drop support for Python 2.7, 3.5, 3.6.


4.4 (2022-12-02)
================

- Add support for Python 3.8, 3.9, 3.10, 3.11.

- Drop support for Python 3.4.

- Drop support for ``python setup.py test`` to run the tests. (#23)

- Drop support for installing this package without having ``setuptools``.


4.3 (2018-10-30)
================

- Add support for Python 3.6 and 3.7.

- Drop support for Python 3.3.


4.2.0 (2016-12-07)
==================

- Add support for Python 3.5.

- Drop support for Python 2.6 and 3.2.


4.1.0 (2015-04-16)
==================

- Add ``--version`` command line option (fixes
  https://github.com/zopefoundation/zdaemon/issues/4).

- ``kill`` now accepts signal names, not just numbers
  (https://github.com/zopefoundation/zdaemon/issues/11).

- Restore ``logreopen`` as an alias for ``kill USR2`` (removed in version
  3.0.0 due to lack of tests):
  https://github.com/zopefoundation/zdaemon/issues/10.

- Make ``logreopen`` also reopen the transcript log:
  https://github.com/zopefoundation/zdaemon/issues/9.

- Reopen event log on ``logreopen`` or ``reopen_transcript``:
  https://github.com/zopefoundation/zdaemon/issues/8.

- Help message for ``reopen_transcript``
  (https://github.com/zopefoundation/zdaemon/issues/5).

- Fix race condition where ``stop`` would be ignored if the daemon
  manager was waiting before respawning a crashed program.
  https://github.com/zopefoundation/zdaemon/issues/13.

- Partially fix delayed deadlock when the transcript file runs into a
  full disk (https://github.com/zopefoundation/zdaemon/issues/1).

- Fix test suite leaving stale processes behind
  (https://github.com/zopefoundation/zdaemon/issues/7).


4.0.1 (2014-12-26)
==================

- Add support for PyPy.  (PyPy3 is pending release of a fix for:
  https://bitbucket.org/pypy/pypy/issue/1946)

- Add support for Python 3.4.

- Add ``-t/--transcript`` command line option.

- zdaemon can now be invoked as a module as in ``python -m zdaemon ...``

4.0.0 (2013-05-10)
==================

- Add support for Python 3.2.

4.0.0a1 (2013-02-15)
====================

- Add tox support and MANIFEST.in for proper releasing.

- Add Python 3.3 support.

- Drop Python 2.4 and 2.5 support.

3.0.5 (2012-11-27)
==================

- Fixed: the status command didn't return a non-zero exit status when
  the program wasn't running. This made it impossible for other
  software (e.g. Puppet) to tell if a process was running.

3.0.4 (2012-07-30)
==================

- Fixed: The start command exited with a zero exit status even when
  the program being started failed to start (or exited imediately).

3.0.3 (2012-07-10)
==================

- Fixed: programs started with zdaemon couldn't, themselves, invoke
  zdaemon.

3.0.2 (2012-07-10)
==================

Fail :(

3.0.1 (2012-06-08)
==================

- Fixed:

  The change in 2.0.6 to set a user's supplemental groups broke common
  configurations in which the effective user was set via ``su`` or
  ``sudo -u`` prior to invoking zdaemon.

  Now, zdaemon doesn't set groups or the effective user if the
  effective user is already set to the configured user.

3.0.0 (2012-06-08)
==================

- Added an option, ``start-test-program`` to supply a test command to
  test whether the program managed by zdaemon is up and operational,
  rather than just running.  When starting a program, the start
  command doesn't return until the test passes. You could, for
  example, use this to wait until a web server is actually accepting
  connections.

- Added a ``start-timeout`` option to error if a program takes too long to
  start. This is especially useful in combination with the
  ``start-test-program`` option.

- Added an option, stop-timeout, to control how long to wait
  for a graceful shutdown.

  Previously, this was controlled by backoff-limit, which didn't make
  much sense.

- Several undocumented, untested, and presumably unused features were removed.

2.0.6 (2012-06-07)
==================

- Fixed: When the ``user`` option was used to run as a particular
  user, supplemental groups weren't set to the user's supplemental
  groups.

2.0.5 (2012-06-07)
==================

(Accidental release. Please ignore.)

2.0.4 (2009-04-20)
==================

- Version 2.0.3 broke support for relative paths to the socket (``-s``
  option and ``socket-name`` parameter), now relative paths work again
  as in version 2.0.2.

- Fixed change log format, made table of contents nicer.

- Fixed author's email address.

- Removed zpkg stuff.


2.0.3 (2009-04-11)
==================

- Added support to bootstrap on Jython.

- If the run directory does not exist it will be created. This allow to use
  `/var/run/mydaemon` as run directory when /var/run is a tmpfs (LP #318118).

Bugs Fixed
----------

- No longer uses a hard-coded file name (/tmp/demo.zdsock) in unit tests.
  This lets you run the tests on Python 2.4 and 2.5 simultaneously without
  spurious errors.

- make -h work again for both runner and control scripts.
  Help is now taken from the __doc__ of the options class users by
  the zdaemon script being run.

2.0.2 (2008-04-05)
==================

Bugs Fixed
----------

- Fixed backwards incompatible change in handling of environment option.

2.0.1 (2007-10-31)
==================

Bugs Fixed
----------

- Fixed test renormalizer that did not work in certain cases where the
  environment was complex.

2.0.0 (2007-07-19)
==================

- Final release for 2.0.0.

2.0a6 (2007-01-11)
==================

Bugs Fixed
----------

- When the user option was used, it only affected running the daemon.

2.0a3, 2.0a4, 2.0a5 (2007-01-10)
================================

Bugs Fixed
----------

- The new (2.0) mechanism used by zdaemon to start the daemon manager
  broke some applications that extended zdaemon.

- Added extra checks to deal with programs that extend zdaemon
  and copy the schema and thus don't see updates to the ZConfig schema.

2.0a2 (2007-01-10)
==================

New Features
------------

- Added support for setting environment variables in the configuration
  file.  This is useful when zdaemon is used to run programs that need
  environment variables set (e.g. LD_LIBRARY_PATH).

- Added a command to rotate the transcript log.

2.0a1 (2006-12-21)
==================

Bugs Fixed
----------

- In non-daemon mode, start hung, producing annoying dots
  when the program exited.

- The start command hung producing annoying dots if the daemon failed
  to start.

- foreground and start had different semantics because one used
  os.system and another used os.spawn

New Features
------------

- Documentation

- Command-line arguments can now be supplied to the start and
  foreground (fg) commands

- zdctl now invokes itself to run zdrun.  This means that it's
  no-longer necessary to generate a separate zdrun script.  This
  especially when the magic techniques to find and run zdrun using
  directory sniffing fail to set the path correctly.

- The daemon mode is now enabled by default.  To get non-daemon mode,
  you have to use a configuration file and set daemon to off
  there. The old -d option is kept for backward compatibility, but is
  a no-op.

1.4a1 (2005-11-21)
==================

- Fixed a bug in the distribution setup file.

1.4a1 (2005-11-05)
==================

- First semi-formal release.

After some unknown release(???)
===============================

- Made 'zdaemon.zdoptions' not fail for --help when __main__.__doc__
  is None.

After 1.1
=========

- Updated test 'testRunIgnoresParentSignals':

 o Use 'mkdtemp' to create a temporary directory to hold the test socket
   rather than creating the test socket in the test directory.
   Hopefully this will be more robust.  Sometimes the test directory
   has a path so long that the test socket can't be created.

 o Changed management of 'donothing.sh'.  This script is now created by
   the test in the temporarily directory with the necessary
   permissions. This is to avoids possible mangling of permissions
   leading to spurious test failures.  It also avoids management of a
   file in the source tree, which is a bonus.

- Rearranged source tree to conform to more usual zpkg-based layout:

  o Python package lives under 'src'.

  o Dependencies added to 'src' as 'svn:externals'.

  o Unit tests can now be run from a checkout.

- Made umask-based test failures due to running as root emit a more
  forceful warning.

1.1 (2005-06-09)
================

- SVN tag:  svn://svn.zope.org/repos/main/zdaemon/tags/zdaemon-1.1

- Tagged to make better 'svn:externals' linkage possible.

To-Dos
======

More docs:

- Document/demonstrate some important features, such as:

  - working directory

Bugs:

- help command
