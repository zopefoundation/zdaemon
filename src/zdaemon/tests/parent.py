import time
import os
import sys

donothing_contents = """\
#!/bin/sh
while [ "1" -ne "2" ]; do
   sleep 10
done
"""


def main():
    # dummy zdctl startup of zdrun
    shutup()
    file = os.path.normpath(os.path.abspath(sys.argv[0]))
    tmp = sys.argv[1]
    dir = os.path.dirname(file)
    zctldir = os.path.dirname(dir)
    zdrun = os.path.join(zctldir, 'zdrun.py')
    donothing = os.path.join(tmp, 'donothing.sh')
    fd = os.open(donothing, os.O_WRONLY | os.O_CREAT, 0o700)
    os.write(fd, donothing_contents.encode())
    os.close(fd)
    args = [sys.executable, zdrun]
    args += ['-d', '-b', '10', '-s', os.path.join(tmp, 'testsock'),
             '-x', '0,2', '-z', dir, donothing]
    flag = os.P_NOWAIT
    os.spawnvpe(flag, args[0], args,
                dict(os.environ, PYTHONPATH=':'.join(sys.path)),
                )
    while 1:
        # wait to be signaled
        time.sleep(1)


def shutup():
    os.close(0)
    sys.stdin = sys.__stdin__ = open("/dev/null")
    try:  # PEP 446, Python >= 3.4
        os.set_inheritable(sys.stdin.fileno(), True)
    except AttributeError:
        pass
    os.close(1)
    sys.stdout = sys.__stdout__ = open("/dev/null", "w")
    try:  # PEP 446, Python >= 3.4
        os.set_inheritable(sys.stdout.fileno(), True)
    except AttributeError:
        pass
    os.close(2)
    sys.stderr = sys.__stderr__ = open("/dev/null", "w")
    try:  # PEP 446, Python >= 3.4
        os.set_inheritable(sys.stderr.fileno(), True)
    except AttributeError:
        pass

if __name__ == '__main__':
    main()
