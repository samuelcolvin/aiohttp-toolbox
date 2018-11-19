from importlib.machinery import SourceFileLoader
from pathlib import Path
from setuptools import setup

description = 'Tools for aiohttp I want to reuse.'
THIS_DIR = Path(__file__).resolve().parent
try:
    long_description = '\n\n'.join([
        THIS_DIR.joinpath('README.rst').read_text(),
        THIS_DIR.joinpath('HISTORY.rst').read_text()
    ])
except FileNotFoundError:
    long_description = description

# avoid loading the package before requirements are installed:
version = SourceFileLoader('version', 'atoolbox/version.py').load_module()

setup(
    name='aiohttp-toolbox',
    version=str(version.VERSION),
    description=description,
    long_description=long_description,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Unix',
        'Operating System :: POSIX :: Linux',
        'Environment :: MacOS X',
        'Topic :: Internet',
    ],
    author='Samuel Colvin',
    author_email='s@muelcolvin.com',
    url='https://github.com/samuelcolvin/aiohttp-tools',
    license='MIT',
    packages=[
        'atoolbox',
        'atoolbox.bread',
        'atoolbox.db',
    ],
    entry_points="""
        [console_scripts]
        atoolbox=atoolbox.cli:cli
        aiohttp_toolbox=atoolbox.cli:cli
    """,
    python_requires='>=3.6',
    zip_safe=True,
    install_requires=[
        'aiodns>=1.1.1',
        'aiohttp>=3.4.4',
        'aiohttp-session>=2.6.0',
        'arq>=0.14',
        'asyncpg>=0.17.0',
        'buildpg>=0.0.2',
        'cchardet>=2.1.4',
        'cryptography>=2.4.1',
        'pydantic[email]>=0.15',
        'raven>=6.9.0',
        'raven-aiohttp>=0.7.0',
        'uvloop>=0.11.2',
    ],
)
