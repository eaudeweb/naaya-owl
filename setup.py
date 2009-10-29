from setuptools import setup, find_packages

setup(
    name = "NyOwl",
    version = "0.1",
    packages = find_packages(),
    author = "Alex Morega",
    author_email = "alex.morega@eaudeweb.ro",
    description = "Nightly test runner for Naaya",
    license = "BSD License",
    entry_points = {
        'console_scripts': [
            'nyowl = naaya_owl.cmd:main',
        ],
    },
)

