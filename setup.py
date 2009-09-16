#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='ltprotocol',
    version='0.2.1',
    description='Twisted-based client and server for protocols which begin with a length and type field',
    author='David Underhill',
    author_email='dgu@cs.stanford.edu',
    url='http://www.dound.com/projects/python/ltprotocol/',
    packages=find_packages(exclude='tests'),
    long_description="""\
Provides a Twisted-based client and server implementation for protocols which
begin with a legnth and type field.  Create your protocol by constructing an
LTProtocol with a list of LTMessage objects which specify your protocol.  Use
LTTwistedServer and LTTwistedClient to create a server or client.
      """,
      classifiers=[
          "License :: OSI Approved :: GNU General Public License (GPL)",
          "Programming Language :: Python",
          "Development Status :: 4 - Beta",
          "Intended Audience :: Developers",
          "Topic :: Internet",
      ],
      keywords='networking twisted protocol nonblocking internet length type',
      license='GPL',
      install_requires=[
        'setuptools',
        'twisted',
      ])
