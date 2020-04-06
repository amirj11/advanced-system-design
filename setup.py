from setuptools import setup, find_packages

setup(
    name='cortex',
    version='1.0.0',
    author='Amir Johnpur',
    description='A package for uploading brain snaphots to a server, with multiple server-side components.',
    packages=find_packages(),
    tests_require=['pytest'],
)
