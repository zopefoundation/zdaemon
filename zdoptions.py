"""Option processing for zdaemon and related code."""

import os
import sys
import getopt

import ZConfig

class ZDOptions:

    doc = None
    progname = None
    configfile = None
    schemadir = None
    schemafile = "schema.xml"
    schema = None
    configroot = None

    # Class variable to control automatic processing of a <logger>
    # section.  This should be the (possibly dotted) name of something
    # accessible from configroot, typically "logger".
    logsectionname = None

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
        self.add(None, None, "h", "help", self.help)
        self.add("configfile", None, "C:", "configure=")

    def help(self, dummy):
        """Print a long help message (self.doc) to stdout and exit(0).

        Occurrences of "%s" in self.doc are replaced by self.progname.
        """
        doc = self.doc
        if doc.find("%s") > 0:
            doc = doc.replace("%s", self.progname)
        print doc,
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
            if self.default_map.has_key(name):
                del self.default_map[name]
            if self.required_map.has_key(name):
                del self.required_map[name]
        if confname:
            for n, cn in self.names_list[:]:
                if cn == confname:
                    self.names_list.remove((n, cn))
        if short:
            key = "-" + short[0]
            if self.options_map.has_key(key):
                del self.options_map[key]
        if long:
            key = "--" + long
            if key[-1] == "=":
                key = key[:-1]
            if self.options_map.has_key(key):
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
        """

        if flag is not None:
            if handler is not None:
                raise ValueError, "use at most one of flag= and handler="
            if not long and not short:
                raise ValueError, "flag= requires a command line flag"
            if short and short.endswith(":"):
                raise ValueError, "flag= requires a command line flag"
            if long and long.endswith("="):
                raise ValueError, "flag= requires a command line flag"
            handler = lambda arg, flag=flag: flag

        if short and long:
            if short.endswith(":") != long.endswith("="):
                raise ValueError, "inconsistent short/long options: %r %r" % (
                    short, long)

        if short:
            if short[0] == "-":
                raise ValueError, "short option should not start with '-'"
            key, rest = short[:1], short[1:]
            if rest not in ("", ":"):
                raise ValueError, "short option should be 'x' or 'x:'"
            key = "-" + key
            if self.options_map.has_key(key):
                raise ValueError, "duplicate short option key '%s'" % key
            self.options_map[key] = (name, handler)
            self.short_options.append(short)

        if long:
            if long[0] == "-":
                raise ValueError, "long option should not start with '-'"
            key = long
            if key[-1] == "=":
                key = key[:-1]
            key = "--" + key
            if self.options_map.has_key(key):
                raise ValueError, "duplicate long option key '%s'" % key
            self.options_map[key] = (name, handler)
            self.long_options.append(long)

        if name:
            if not hasattr(self, name):
                setattr(self, name, None)
            self.names_list.append((name, confname))
            if default is not None:
                self.default_map[name] = default
            if required:
                self.required_map[name] = required

    def realize(self, args=None, progname=None, doc=None):
        """Realize a configuration.

        Optional arguments:

        args     -- the command line arguments, less the program name
                    (default is sys.argv[1:])

        progname -- the program name (default is sys.argv[0])

        doc      -- usage message (default is __main__.__doc__)
        """

         # Provide dynamic default method arguments
        if args is None:
            args = sys.argv[1:]
        if progname is None:
            progname = sys.argv[0]
        if doc is None:
            import __main__
            doc = __main__.__doc__
        self.progname = progname
        self.doc = doc

        # Call getopt
        try:
            self.options, self.args = getopt.getopt(
                args, "".join(self.short_options), self.long_options)
        except getopt.error, msg:
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
                except ValueError, msg:
                    self.usage("invalid value for %s %r: %s" % (opt, arg, msg))
            if name and arg is not None:
                if getattr(self, name) is not None:
                    self.usage("conflicting command line option %r" % opt)
                setattr(self, name, arg)

        if self.configfile is not None:
            # Process config file
            if self.schema is None:
                # Load schema
                if self.schemadir is None:
                    self.schemadir = os.path.dirname(__file__)
                self.schemafile = os.path.join(self.schemadir, self.schemafile)
                self.schema = ZConfig.loadSchema(self.schemafile)

            # Load configuration
            try:
                self.configroot, xxx = ZConfig.loadConfig(self.schema,
                                                          self.configfile)
            except ZConfig.ConfigurationError, msg:
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

    def load_logconf(self, sectname="logger"):
        parts = sectname.split(".")
        obj = self.configroot
        for p in parts:
            if obj == None:
                break
            obj = getattr(obj, p)
        self.config_logger = obj
        if obj is not None:
            import zLOG
            zLOG.set_initializer(self.log_initializer)
            zLOG.initialize()

    def log_initializer(self):
        from zLOG import EventLogger
        logger = self.config_logger()
        for handler in logger.handlers:
            if hasattr(handler, "reopen"):
                handler.reopen()
        EventLogger.event_logger.logger = logger


def _test():
    # Stupid test program
    z = ZDOptions()
    z.add("program", "zdctl.program", "p:", "program=")
    print z.names_list
    z.realize()
    names = z.names_list[:]
    names.sort()
    for name, confname in names:
        print "%-20s = %.56r" % (name, getattr(z, name))

if __name__ == "__main__":
    __file__ = sys.argv[0]
    _test()
