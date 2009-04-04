entry_points = """
[console_scripts]
zdctl = zdaemon.zdctl:main
zdrun = zdaemon.zdrun:main
"""

def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

try:
    from setuptools import setup
    setuptools_options = dict(
        zip_safe=False,
        entry_points=entry_points,
        )
except ImportError:
    from distutils.core import setup
    setuptools_options = {}

name = "zdaemon"
setup(
    name=name,
    version="1.4a1",
    url="http://www.python.org/pypi/zdaemon",
    license="ZPL 2.1",
    description="Daemon process control library and tools",
    author="Zope Corporation and Contributors",
    author_email="zope3-dev@zope.org",
    long_description=(
        read('README.txt')
        + '\n' +
        read('CHANGES.txt')
        + '\n' +
        'Download\n'
        '**********************\n'
        ),

    packages=["zdaemon", "zdaemon.tests"],
    package_dir={"": "src"},
    install_requires=["ZConfig"],
    tests_require=["zope.testing"],
    
    **setuptools_options)
