#! /bin/sh
#
# Copy this script into the /etc/rc.d/init.d directory and edit the
# description line below and the pathnames; then run chkconfig(8).
#
# chkconfig: 345 90 10
# description: start a Zope-related server (Zope, ZEO or ZRS)

# Edit to indicate which Python to use
PYTHON=/usr/local/bin/python2.2

# Edit to indicate where the core Zope software lives
ZOPE_HOME=$HOME/projects/Zope

# Edit to indicate where your Zope instance lives
INSTANCE_HOME=$HOME/projects/Zope

# Edit to indicate where your config file is
CONFIG_LOCATION=$INSTANCE_HOME/sample.conf

# You shouldn't need to edit these
SOFTWARE_HOME=$ZOPE_HOME/lib/python
ZDCTL=$SOFTWARE_HOME/zdaemon/zdctl.py
CMD="$PYTHON $ZDCTL -C $CONFIG_LOCATION"

# Parse the command line
case $1 in
[a-z]*[a-z]) $CMD "$@";;
-i) $CMD;;
*)  echo "Usage: $0 start|stop|restart|status|help|etc."
    echo "       $0 -i starts an interactive zdctl shell."
   ;;
esac
