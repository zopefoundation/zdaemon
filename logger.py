##############################################################################
#
# Copyright (c) 2003 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Abbreviated PEP 282 logger that uses zLOG."""

import os
import sys

import zLOG


class Logger:

    # Log messages with various severities.
    # This uses zLOG, but the API is a simplified version of PEP 282

    def critical(self, msg):
        """Log a critical message."""
        self._log(msg, zLOG.PANIC)

    def error(self, msg):
        """Log an error message."""
        self._log(msg, zLOG.ERROR)

    def exception(self, msg):
        """Log an exception (an error message with a traceback attached)."""
        self._log(msg, zLOG.ERROR, error=sys.exc_info())

    def warn(self, msg):
        """Log a warning message."""
        self._log(msg, zLOG.PROBLEM)

    def info(self, msg):
        """Log an informational message."""
        self._log(msg, zLOG.INFO)

    def debug(self, msg):
        """Log a debugging message."""
        self._log(msg, zLOG.DEBUG)

    def _log(self, msg, severity=zLOG.INFO, error=None):
        """Internal: generic logging function."""
        zLOG.LOG("ZD:%d" % os.getpid(), severity, msg, "", error)
