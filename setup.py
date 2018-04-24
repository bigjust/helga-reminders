import functools
import pkg_resources

from setuptools import setup, find_packages

setup(
    name='helga-reminders',
    version='0.1.1',
    description="A helga command for scheduling one time or recurring reminders",
    classifiers=[
        'Development Status :: 4 - Beta',
        'Topic :: Communications :: Chat :: Internet Relay Chat',
        'Framework :: Twisted',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    keywords='helga reminders',
    author="Shaun Duncan",
    author_email="shaun.duncan@gmail.com",
    url="https://github.com/shaunduncan/helga-reminders",
    packages=find_packages(),
    py_modules=['helga_reminders'],
    include_package_data=True,
    install_requires=[
        'pytz',
    ],
    zip_safe=True,
    entry_points=dict(
        helga_plugins=[
            'reminders = helga_reminders:reminders',
        ],
    ),
)
