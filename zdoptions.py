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
        self.table = {}
        self.short_options = {}
        self.long_options = {}
        self.add("help", "h", "help", handler=self.help)
        self.add("configfile", "C:", "configure=")

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
            name,                       # attribute name on self
            short=None,                 # short option name
            long=None,                  # long option name
            confname=None,              # name in ZConfig (may be dotted)
            handler=None,               # handler (defaults to string)
            required=None,              # message issed if missing
            ):
        if self.table.has_key(name):
            raise ValueError, "duplicate option name: " + repr(name)
        if short:
            if short[0] == "-":
                raise ValueError, "short option should not start with '-'"
            key, rest = short[:1], short[1:]
            if rest and rest != ":":
                raise ValueError, "short option should be 'x' or 'x:'"
            if self.short_options.has_key(key):
                raise ValueError, "duplicate short option: " + repr(short)
        if long:
            if long[0] == "-":
                raise ValueError, "long option should not start with '-'"
            key = long
            if key[-1] == "=":
                key = key[:-1]
            if self.long_options.has_key(key):
                raise ValueError, "duplicate long option: " + repr(long)
        if short and long:
            if short.endswith(":") != long.endswith("="):
                raise ValueError, "inconsistent short/long options: %r %r" % (
                    short, long)
        self.table[name] = (short, long, confname, handler, required)
        if short:
            self.short_options[short[0]] = name
        if long:
            key = long
            if key[-1] == "=":
                key = key[:-1]
            self.long_options[key] = name

    def realize(self, args=None, progname=None, doc=None):
        """Realize a configuration."""

        if args is None:
            args = sys.argv[1:]
        if progname is None:
            self.progname = sys.argv[0]
        if doc is None:
            import __main__
            doc = __main__.__doc__
        self.progname = progname
        self.doc = doc

        # Construct short and long option tables for getopt
        shorts = ""
        longs = []
        for name, (short, long, xxx, xxx, xxx) in self.table.items():
            if short:
                shorts += short
            if long:
                longs.append(long)

        # Call getopt
        try:
            self.options, self.args = getopt.getopt(args, shorts, longs)
        except getopt.error, msg:
            self.usage(msg)

        # Process options returned by getopt
        for o, a in self.options:
            if o.startswith("--"):
                name = self.long_options[o[2:]]
            elif o.startswith("-"):
                name = self.short_options[o[1:]]
            else:
                self.usage("unrecognized option " + repr(o))
            handler = self.table[name][3]
            if handler is None:
                value = a
            else:
                try:
                    value = handler(a)
                except ValueError, msg:
                    self.usage("invalid value for %s %s: %s" % (o, a, msg))
            setattr(self, name, value)

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
        for name in self.table.keys():
            if not hasattr(self, name) or getattr(self, name) is None:
                confname = self.table[name][2]
                parts = confname.split(".")
                obj = self.configroot
                for part in parts:
                    if obj is None:
                        break
                    # If this raises AttributeError, that's not a user error!
                    obj = getattr(obj, part)
                setattr(self, name, obj)


def _test():
    # Stupid test program
    z = ZDOptions()
    z.add("program", "p:", "program=", "zdctl.program")
    z.realize()
    names = z.table.keys()
    names.sort()
    for name in names:
        print "%-20s = %.56r" % (name, getattr(z, name))

if __name__ == "__main__":
    __file__ = sys.argv[0]
    _test()
