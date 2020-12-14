#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
from setuptools import setup, find_packages
import os

# Parse the version from the main __init__.py
with open('nrt/__init__.py') as f:
    for line in f:
        if line.find("__version__") >= 0:
            version = line.split("=")[1].strip()
            version = version.strip('"')
            version = version.strip("'")
            continue


with codecs.open('README.rst', encoding='utf-8') as f:
    readme = f.read()

setup(name='nrt',
      version=version,
      description=u"Online monitoring with xarray",
      long_description=readme,
      keywords='sentinel2, xarray, datacube, monitoring, change',
      author=u"Loic Dutrieux",
      author_email='loic.dutrieux@gmail.com',
      url='https://jeodpp.jrc.ec.europa.eu/apps/gitlab/dutrilo/nrt.git',
      license='GPLv3',
      classifiers=[
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
      ],
      packages=find_packages(),
      package_data={'nrt': ['data/*.nc']},
      install_requires=[
          'numpy',
          'xarray',
          'netCDF4',
          'pandas'
      ])
