#! /usr/bin/env python3.5
from setuptools import setup


with open('README.rst', encoding='utf-8') as readme_file:
    long_description = readme_file.read()

setup(
    name='github-backup',
    version='0.1.0',
    url='https://github.com/HarkonenBade/github-backup',
    license='MIT',
    author='Thomas Bytheway',
    author_email='github@harkonen.net',
    description='A basic solution for backing up github repos',
    long_description=long_description,
    install_requires=['agithub', 'gitpython', 'pyyaml'],
    tests_require=['nose', 'coverage'],
)
