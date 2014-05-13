from setuptools import setup, find_packages

install_requires = [
    'urwid',
]

setup(
    name="installer",
    version="0.1",
    description="A multi-frontend installer",
    license="GPLv2",
    author="Franck Bui",
    author_email="fbui@mandriva.com",
    packages=find_packages(),
    include_package_data=True,
    install_requires=install_requires,
    scripts = ['bin/installer']
)
