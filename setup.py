from setuptools import setup, find_packages

setup(
    name='bakrest',
    version='0.1.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'bakrest=bakrest.bakrest:main',
        ]
    },
    author='chrisg123',
    description="Upload and restore a SQL Server .bak to a remote server",
    url="https://github.com/chrisg123/bakrest",
    install_requires=[
        'requests'
    ]
)
