#!/usr/bin/env python
##############################################################################
#
# Copyright (c) 2001 Zope Corporation and Contributors. All Rights Reserved.
# 
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
# 
##############################################################################
"""

zinit, slightly smarter server manager and ZServer startup script.

  zinit will:

    - Fork a parent and a child

    - restart the child if it dies

    - write a pid file so you can kill (the parent)

    - reports the childs pid to stdout so you can kill that too

TODO

  - Have the parent reap the children when it dies

  - etc.

"""

from Daemon import run

# XXX Is the following a useful feature?

def main():
    import sys
    argv=sys.argv[1:]
    if argv and argv[0][:2]=='-p':
        pidf=argv[0][2:]
        del argv[0]
    else:
        pidf=''

    if not argv:
        print __doc__ % vars()
        print
        print 'Error: no script given'
            
    run(argv, pidf)

if __name__ == '__main__': main()
