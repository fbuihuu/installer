from setuptools import setup, find_packages
from DistUtilsExtra.command import *
from installer import get_version

install_requires = [
    'urwid',
]

setup(
    name="installer",
    version=get_version(),
    description="A multi-frontend installer",
    license="GPLv2",
    author="Franck Bui",
    author_email="fbui@mandriva.com",
    packages=find_packages(),
    include_package_data=True,
    install_requires=install_requires,
    scripts=['bin/installer'],
    cmdclass={ "build"      : build_extra.build_extra,
               "build_i18n" : build_i18n.build_i18n },
)
