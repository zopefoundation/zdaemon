#! /bin/sh
#
# Copy this script into the /etc/rc.d/init.d directory and edit the
# description line below and the pathnames; then run chkconfig(8).
#
# chkconfig: 345 90 10
# description: start a Zope-related server (Zope, ZEO or ZRS)
#
# (XXX If there are more conventional names for some of the envvars
# below, please check in a fix.  INSTANCE_HOME, ZOPE_HOME and
# SOFTWARE_HOME still confuse me.)

# Edit to indicate which Python to use
PYTHON=/usr/local/bin/python2.2

# Edit to indicate where your Zope modules are
ZOPELIB=$HOME/projects/ZODB3

# Edit to indicate where your config file is (may be a URL too)
CONFIGFILE=$ZOPELIB/zdaemon/sample.conf

# You shouldn't need to edit these
ZDCTL=$ZOPELIB/zdaemon/zdctl.py
CMD="$PYTHON $ZDCTL -C $CONFIGFILE"

# Parse the command line
case $1 in
[a-z]*[a-z]) $CMD "$@";;
-i) $CMD;;
*)  echo "Usage: $0 start|stop|restart|status|help|etc."
    echo "       $0 -i starts an interactive zdctl shell."
   ;;
esac
