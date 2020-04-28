#!/usr/bin/env python

"""The setup script."""

from setuptools import setup

with open("requirements.txt") as f:
    requirements = [x for x in f.read().splitlines() if x and x[0] not in "-# "]


setup(
    # There are standard setuptools entries
    install_requires=requirements,
    setup_cfg=True,
)
