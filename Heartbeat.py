##############################################################################
#
# Copyright (c) 2001, 2002 Zope Corporation and Contributors.
# All Rights Reserved.
# 
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
# 
##############################################################################
'''Heartbeat feature for process management daemon.
'''

from ZDaemonLogging import pstamp

# This is the number of seconds between the parent pulsing the child.
# Set to 0 to deactivate pulsing.

BEAT_DELAY = 0
VERBOSE = 1
activities = []

# If you want the parent to 'pulse' Zope every 'BEAT_DELAY' seconds,
# put the URL to the method you want to call here.  This can be any
# methodish object that can be called through the web.  Format is:
#
# activities = (("http://x/method", "username", "password"),)
#
# username and password may be None if the method does not require
# authentication. 

# activities = (('http://localhost:9222/Heart/heart', 'michel', '123'),
#               )

def heartbeat():
    #print 'tha-thump'
    if activities:
        import ZPublisher
        for a in activities:
            try:
                result = ZPublisher.Client.call(a[0], a[1], a[2])
            except:
                pstamp('activity %s failed!' % a[0], zLOG.WARNING)
                return

            if result and VERBOSE:
                pstamp('activity %s returned: %s' % (a[0], result),
                       zLOG.BLATHER)

