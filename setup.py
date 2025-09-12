#!/usr/bin/env python3
from setuptools import setup


setup(
    name="kubectl",
    version="0.0.7",
    author="Jean-Baptiste Langlois",
    author_email="jean-baptiste.langlois@imtf.com",
    description="Helper which mimics Kubectl behaviour",
    url="https://github.com/imtf-group/kubectl-helper.git",
    packages=['kubectl'],
    package_dir={'kubectl': 'kubectl'},
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        'requests==2.32.5',
        'kubernetes==33.1.0'
    ]
)
