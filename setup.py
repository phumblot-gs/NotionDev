#!/usr/bin/env python
"""Setup script for NotionDev - keeping for backward compatibility"""

from setuptools import setup, find_packages

# Read the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="notion-dev",
    version="1.0.2",
    author="Your Name",
    author_email="your.email@example.com",
    description="Integration tool for Notion, Asana and Git workflows",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/notion-dev",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=[
        "asana>=3.2.0",
        "notion-client>=2.2.1",
        "click>=8.1.7",
        "pyyaml>=6.0.1",
        "rich>=13.7.0",
        "requests>=2.31.0",
        "gitpython>=3.1.40",
    ],
    entry_points={
        "console_scripts": [
            "notion-dev=notion_dev.cli.main:cli",
        ],
    },
)
