try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name="zdaemon",
    version="1.3",
    url="http://svn.zope.org/zdaemon",
    license="ZPL 2.1",
    description="daemon process control library and tools",
    long_description=open("README.txt").read(),
    author="Zope Corporation and Contributors",
    author_email="zope3-dev@zope.org",

    packages=["zdaemon", "zdaemon.tests"],
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=["ZConfig", "zope.testing"],
    zip_safe=False,
    )
