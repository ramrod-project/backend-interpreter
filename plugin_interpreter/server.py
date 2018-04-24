"""Interpreter server

Starts the main interpreter web server. This initially creates a
Supervisor class object, loads all of the plugins from the ./plugins
folder, and hands them off to the Supervisor object for
server initialization.
"""
from os import path
from sys import argv

from src import supervisor


if __name__ == '__main__':
    """Entry point, creates Supervisor and begins process monitoring"""
    try:
        if type(argv[1]) is not str:
            raise TypeError
    except IndexError:
        print("Please provide one plugin as an argument!")
        exit(99)

    supervisor_controller = supervisor.SupervisorController(argv[1])

    try:
        supervisor_controller.create_servers()
    except KeyError:
        exit(99)
    supervisor_controller.spawn_servers()

    supervisor_controller.monitor()
