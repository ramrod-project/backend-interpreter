"""Main server module

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

    if type(argv[1]) is not str:
        raise TypeError

    supervisor_controller = supervisor.SupervisorController(argv[1])

    supervisor_controller.create_servers()
    supervisor_controller.spawn_servers()

    supervisor_controller.monitor()
