#! /usr/bin/env python

import signal

signal.signal(signal.SIGTERM, signal.SIG_IGN)

while True:
    signal.pause()
