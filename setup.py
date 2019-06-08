import os
import sys
from setuptools import find_packages, setup
from arcdiscvist import __version__


# We use the README as the long_description
readme_path = os.path.join(os.path.dirname(__file__), "README.rst")


setup(
    name='arcdiscvist',
    version=__version__,
    author='Andrew Godwin',
    author_email='andrew@aeracode.org',
    description='Archiving and indexing tool',
    long_description=open(readme_path).read(),
    license='BSD',
    zip_safe=False,
    packages=find_packages(),
    include_package_data=True,
    install_requires=["click"],
    entry_points={'console_scripts': [
        'arcdiscvist = arcdiscvist.cli:main',
    ]},
)
