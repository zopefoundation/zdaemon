"""Option processing for zdaemon and related code."""

import os
import sys
import getopt

import ZConfig

class ZDOptions:

    doc = None
    progname = None
    configfile = None
    schemafile = "schema.xml"

    def __init__(self):
        self.names_list = []
        self.short_options = []
        self.long_options = []
        self.options_map = {}
        self.add(None, None, "h", "help", self.help)
        self.add("configfile", None, "C:", "configure=")

    def help(self, value):
        print self.doc.strip()
        sys.exit(0)

    def usage(self, msg):
        sys.stderr.write(str(msg) + "\n")
        progname = self.progname
        if progname is None:
            progname = sys.argv[0]
        sys.stderr.write("for more help, use %s --help\n" % progname)
        sys.exit(2)

    def add(self,
            name=None,                  # attribute name on self
            confname=None,              # name in ZConfig (may be dotted)
            short=None,                 # short option name
            long=None,                  # long option name
            handler=None,               # handler (defaults to string)
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
       """

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
            self.options_map[key] = (name, handler)
            self.long_options.append(long)

        if name:
            if not hasattr(self, name):
                setattr(self, name, None)
            self.names_list.append((name, confname))

    def realize(self, args=None, progname=None, doc=None):
        """Realize a configuration."""

         # Provide dynamic default method arguments
        if args is None:
            args = sys.argv[1:]
        if progname is None:
            self.progname = sys.argv[0]
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

        # Process options returned by getopt
        for opt, arg in self.options:
            name, handler = self.options_map[opt]
            if handler is not None:
                try:
                    arg = handler(arg)
                except ValueError, msg:
                    self.usage("invalid value for %s %s: %s" % (opt, arg, msg))
            if name and arg is not None:
                setattr(self, name, arg)

        # Process config file
        if self.configfile is not None:
            # Load schema
            here = os.path.dirname(__file__)
            self.schemafile = os.path.join(here, self.schemafile)
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
