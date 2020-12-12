#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

__version__ = '0.1.2'
description = 'A lib for measuring ACE based IDR operations.'

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Load requirements
with open(path.join(here, 'requirements.txt'), encoding='utf-8') as f:
    requirements = [line.strip() for line in f.readlines()]

setup(
    name='ace-metrics',

    version=__version__,

    description=description,
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/seanmcfeely/ace-metrics',
    author='Sean McFeely',
    author_email='mcfeelynaes@gmail.com',
    license='GNU General Public License v3.0',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3',
    ],
    python_requires='>=3.6',
    keywords='Information Security,ACE,ACE Ecosystem',
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    scripts=['ace-metrics']
)

