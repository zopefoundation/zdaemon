##############################################################################
#
# Copyright (c) 2003 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Option processing for zdaemon and related code."""
from __future__ import print_function
import os
import sys
import getopt
import signal

import pkg_resources
import ZConfig


class ZDOptions:
    """a zdaemon script.

    Usage: python <script>.py [-C URL] [zdrun-options] [action [arguments]]

    Options:
    -C/--configure URL -- configuration file or URL
    -h/--help -- print usage message and exit
    --version -- print zdaemon version and exit

    Actions are commands like "start", "stop" and "status".  If -i is
    specified or no action is specified on the command line, a "shell"
    interpreting actions typed interactively is started (unless the
    configuration option default_to_interactive is set to false).  Use the
    action "help" to find out about available actions.
    """

    doc = None
    progname = None
    configfile = None
    schemadir = None
    schemafile = "schema.xml"
    schema = None
    confighandlers = None
    configroot = None

    # Class variable to control automatic processing of an <eventlog>
    # section.  This should be the (possibly dotted) name of something
    # accessible from configroot, typically "eventlog".
    logsectionname = None
    config_logger = None  # The configured event logger, if any

    # Class variable deciding whether positional arguments are allowed.
    # If you want positional arguments, set this to 1 in your subclass.
    positional_args_allowed = 0

    def __init__(self):
        self.names_list = []
        self.short_options = []
        self.long_options = []
        self.options_map = {}
        self.default_map = {}
        self.required_map = {}
        self.environ_map = {}
        self.zconfig_options = []
        self.version = pkg_resources.get_distribution("zdaemon").version
        self.add(None, None, "h", "help", self.help)
        self.add(None, None, None, "version", self.print_version)
        self.add("configfile", None, "C:", "configure=")
        self.add(None, None, "X:", handler=self.zconfig_options.append)

    def print_version(self, dummy):
        """Print zdaemon version number to stdout and exit(0)."""
        print(self.version)
        sys.exit(0)

    def help(self, dummy):
        """Print a long help message (self.doc) to stdout and exit(0).

        Occurrences of "%s" in self.doc are replaced by self.progname.
        """
        doc = self.doc
        if not doc:
            doc = "No help available."
        elif doc.find("%s") > 0:
            doc = doc.replace("%s", self.progname)
        print(doc, end='')
        sys.exit(0)

    def usage(self, msg):
        """Print a brief error message to stderr and exit(2)."""
        sys.stderr.write("Error: %s\n" % str(msg))
        sys.stderr.write("For help, use %s -h\n" % self.progname)
        sys.exit(2)

    def remove(self,
               name=None,               # attribute name on self
               confname=None,           # name in ZConfig (may be dotted)
               short=None,              # short option name
               long=None,               # long option name
               ):
        """Remove all traces of name, confname, short and/or long."""
        if name:
            for n, cn in self.names_list[:]:
                if n == name:
                    self.names_list.remove((n, cn))
            if name in self.default_map:
                del self.default_map[name]
            if name in self.required_map:
                del self.required_map[name]
        if confname:
            for n, cn in self.names_list[:]:
                if cn == confname:
                    self.names_list.remove((n, cn))
        if short:
            key = "-" + short[0]
            if key in self.options_map:
                del self.options_map[key]
        if long:
            key = "--" + long
            if key[-1] == "=":
                key = key[:-1]
            if key in self.options_map:
                del self.options_map[key]

    def add(self,
            name=None,                  # attribute name on self
            confname=None,              # name in ZConfig (may be dotted)
            short=None,                 # short option name
            long=None,                  # long option name
            handler=None,               # handler (defaults to string)
            default=None,               # default value
            required=None,              # message if not provided
            flag=None,                  # if not None, flag value
            env=None,                   # if not None, environment variable
            ):
        """Add information about a configuration option.

        This can take several forms:

        add(name, confname)
            Configuration option 'confname' maps to attribute 'name'
        add(name, None, short, long)
            Command line option '-short' or '--long' maps to 'name'
        add(None, None, short, long, handler)
            Command line option calls handler
        add(name, None, short, long, handler)
            Assign handler return value to attribute 'name'

        In addition, one of the following keyword arguments may be given:

        default=...  -- if not None, the default value
        required=... -- if nonempty, an error message if no value provided
        flag=...     -- if not None, flag value for command line option
        env=...      -- if not None, name of environment variable that
                        overrides the configuration file or default
        """

        if flag is not None:
            if handler is not None:
                raise ValueError("use at most one of flag= and handler=")
            if not long and not short:
                raise ValueError("flag= requires a command line flag")
            if short and short.endswith(":"):
                raise ValueError("flag= requires a command line flag")
            if long and long.endswith("="):
                raise ValueError("flag= requires a command line flag")
            handler = lambda arg, flag=flag: flag

        if short and long:
            if short.endswith(":") != long.endswith("="):
                raise ValueError("inconsistent short/long options: %r %r" % (
                    short, long))

        if short:
            if short[0] == "-":
                raise ValueError("short option should not start with '-'")
            key, rest = short[:1], short[1:]
            if rest not in ("", ":"):
                raise ValueError("short option should be 'x' or 'x:'")
            key = "-" + key
            if key in self.options_map:
                raise ValueError("duplicate short option key '%s'" % key)
            self.options_map[key] = (name, handler)
            self.short_options.append(short)

        if long:
            if long[0] == "-":
                raise ValueError("long option should not start with '-'")
            key = long
            if key[-1] == "=":
                key = key[:-1]
            key = "--" + key
            if key in self.options_map:
                raise ValueError("duplicate long option key '%s'" % key)
            self.options_map[key] = (name, handler)
            self.long_options.append(long)

        if env:
            self.environ_map[env] = (name, handler)

        if name:
            if not hasattr(self, name):
                setattr(self, name, None)
            self.names_list.append((name, confname))
            if default is not None:
                self.default_map[name] = default
            if required:
                self.required_map[name] = required

    def realize(self, args=None, progname=None, doc=None,
                raise_getopt_errs=True):
        """Realize a configuration.

        Optional arguments:

        args     -- the command line arguments, less the program name
                    (default is sys.argv[1:])

        progname -- the program name (default is sys.argv[0])

        doc      -- usage message (default is __doc__ of the options class)
        """

        # Provide dynamic default method arguments
        if args is None:
            args = sys.argv[1:]

        if progname is None:
            progname = sys.argv[0]

        self.progname = progname
        self.doc = doc or self.__doc__

        self.options = []
        self.args = []

        # Call getopt
        try:
            self.options, self.args = getopt.getopt(
                args, "".join(self.short_options), self.long_options)
        except getopt.error as msg:
            if raise_getopt_errs:
                self.usage(msg)

        # Check for positional args
        if self.args and not self.positional_args_allowed:
            self.usage("positional arguments are not supported")

        # Process options returned by getopt
        for opt, arg in self.options:
            name, handler = self.options_map[opt]
            if handler is not None:
                try:
                    arg = handler(arg)
                except ValueError as msg:
                    self.usage("invalid value for %s %r: %s" % (opt, arg, msg))
            if name and arg is not None:
                if getattr(self, name) is not None:
                    if getattr(self, name) == arg:
                        # Repeated option, but we don't mind because it
                        # just reinforces what we have.
                        continue
                    self.usage("conflicting command line option %r" % opt)
                setattr(self, name, arg)

        # Process environment variables
        for envvar in self.environ_map.keys():
            name, handler = self.environ_map[envvar]
            if name and getattr(self, name, None) is not None:
                continue
            if envvar in os.environ:
                value = os.environ[envvar]
                if handler is not None:
                    try:
                        value = handler(value)
                    except ValueError as msg:
                        self.usage("invalid environment value for %s %r: %s"
                                   % (envvar, value, msg))
                if name and value is not None:
                    setattr(self, name, value)

        if self.configfile is None:
            self.configfile = self.default_configfile()
        if self.zconfig_options and self.configfile is None:
            self.usage("configuration overrides (-X) cannot be used"
                       " without a configuration file")
        if self.configfile is not None:
            # Process config file
            self.load_schema()
            try:
                self.load_configfile()
            except ZConfig.ConfigurationError as msg:
                self.usage(str(msg))

        # Copy config options to attributes of self.  This only fills
        # in options that aren't already set from the command line.
        for name, confname in self.names_list:
            if confname and getattr(self, name) is None:
                parts = confname.split(".")
                obj = self.configroot
                for part in parts:
                    if obj is None:
                        break
                    # Here AttributeError is not a user error!
                    obj = getattr(obj, part)
                setattr(self, name, obj)

        # Process defaults
        for name, value in self.default_map.items():
            if getattr(self, name) is None:
                setattr(self, name, value)

        # Process required options
        for name, message in self.required_map.items():
            if getattr(self, name) is None:
                self.usage(message)

        if self.logsectionname:
            self.load_logconf(self.logsectionname)

    def default_configfile(self):
        """Return the name of the default config file, or None."""
        # This allows a default configuration file to be used without
        # affecting the -C command line option; setting self.configfile
        # before calling realize() makes the -C option unusable since
        # then realize() thinks it has already seen the option.  If no
        # -C is used, realize() will call this method to try to locate
        # a configuration file.
        return None

    def load_schema(self):
        if self.schema is None:
            # Load schema
            if self.schemadir is None:
                self.schemadir = os.path.dirname(__file__)
            self.schemafile = os.path.join(self.schemadir, self.schemafile)
            self.schema = ZConfig.loadSchema(self.schemafile)

    def load_configfile(self):
        self.configroot, self.confighandlers = \
            ZConfig.loadConfig(self.schema, self.configfile,
                               self.zconfig_options)

    def load_logconf(self, sectname="eventlog"):
        parts = sectname.split(".")
        obj = self.configroot
        for p in parts:
            if obj is None:
                break
            obj = getattr(obj, p)
        self.config_logger = obj
        if obj is not None:
            obj.startup()


class RunnerOptions(ZDOptions):

    uid = gid = None

    def __init__(self):
        ZDOptions.__init__(self)
        self.add("backofflimit", "runner.backoff_limit",
                 "b:", "backoff-limit=", int, default=10)
        self.add("daemon", "runner.daemon", "d", "daemon", flag=1, default=1)
        self.add("forever", "runner.forever", "f", "forever",
                 flag=1, default=0)
        self.add("sockname", "runner.socket_name", "s:", "socket-name=",
                 existing_parent_dirpath, default="zdsock")
        self.add("exitcodes", "runner.exit_codes", "x:", "exit-codes=",
                 list_of_ints, default=[0, 2])
        self.add("user", "runner.user", "u:", "user=")
        self.add("umask", "runner.umask", "m:", "umask=", octal_type,
                 default=0o22)
        self.add("directory", "runner.directory", "z:", "directory=",
                 existing_parent_directory)
        self.add("transcript", "runner.transcript", "t:", "transcript=",
                 default="/dev/null")


# ZConfig datatype

def list_of_ints(arg):
    if not arg:
        return []
    else:
        return list(map(int, arg.split(",")))


def octal_type(arg):
    return int(arg, 8)


def name2signal(string):
    """Converts a signal name to canonical form.

    Signal names are recognized without regard for case:

      >>> name2signal('sighup')
      'SIGHUP'
      >>> name2signal('SigHup')
      'SIGHUP'
      >>> name2signal('SIGHUP')
      'SIGHUP'

    The leading 'SIG' is not required::

      >>> name2signal('hup')
      'SIGHUP'
      >>> name2signal('HUP')
      'SIGHUP'

    Names that are not known cause an exception to be raised::

      >>> name2signal('woohoo')
      Traceback (most recent call last):
      ValueError: could not convert 'woohoo' to signal name

      >>> name2signal('sigwoohoo')
      Traceback (most recent call last):
      ValueError: could not convert 'sigwoohoo' to signal name

    Numeric values are accepted to names as well::

      >>> name2signal(str(signal.SIGHUP))
      'SIGHUP'

    Numeric values that can't be matched to any signal known to Python
    are treated as errors::

      >>> name2signal('-234')
      Traceback (most recent call last):
      ValueError: unsupported signal on this platform: -234

      >>> name2signal(str(signal.NSIG))  #doctest: +ELLIPSIS
      Traceback (most recent call last):
      ValueError: unsupported signal on this platform: ...

    Non-signal attributes of the signal module are not mistakenly
    converted::

      >>> name2signal('_ign')
      Traceback (most recent call last):
      ValueError: could not convert '_ign' to signal name

      >>> name2signal('_DFL')
      Traceback (most recent call last):
      ValueError: could not convert '_DFL' to signal name

      >>> name2signal('sig_ign')
      Traceback (most recent call last):
      ValueError: could not convert 'sig_ign' to signal name

      >>> name2signal('SIG_DFL')
      Traceback (most recent call last):
      ValueError: could not convert 'SIG_DFL' to signal name

      >>> name2signal('getsignal')
      Traceback (most recent call last):
      ValueError: could not convert 'getsignal' to signal name

    """
    try:
        v = int(string)
    except ValueError:
        if "_" in string:
            raise ValueError("could not convert %r to signal name" % string)
        if string.startswith('Signals.'):  # py35 signals are an enum type
            string = string[len('Signals.'):]
        s = string.upper()
        if not s.startswith("SIG"):
            s = "SIG" + s
        v = getattr(signal, s, None)
        if isinstance(v, int):
            return s
        raise ValueError("could not convert %r to signal name" % string)
    if v >= signal.NSIG:
        raise ValueError("unsupported signal on this platform: %s" % string)
    for name in dir(signal):
        if "_" in name:
            continue
        if getattr(signal, name) == v:
            return name
    raise ValueError("unsupported signal on this platform: %s" % string)


def existing_parent_directory(arg):
    path = os.path.expanduser(arg)
    if os.path.isdir(path):
        # If the directory exists, that's fine.
        return path
    parent, tail = os.path.split(path)
    if os.path.isdir(parent):
        return path
    raise ValueError('%s is not an existing directory' % arg)


def existing_parent_dirpath(arg):
    path = os.path.expanduser(arg)
    dir = os.path.dirname(path)
    parent, tail = os.path.split(dir)
    if not parent:
        # relative pathname
        return path
    if os.path.isdir(parent):
        return path
    raise ValueError('The directory named as part of the path %s '
                     'does not exist.' % arg)


def _test():  # pragma: nocover
    # Stupid test program
    z = ZDOptions()
    z.add("program", "zdctl.program", "p:", "program=")
    print(z.names_list)
    z.realize()
    names = z.names_list[:]
    names.sort()
    for name, confname in names:
        print("%-20s = %.56r" % (name, getattr(z, name)))

if __name__ == "__main__":
    __file__ = sys.argv[0]
    _test()
