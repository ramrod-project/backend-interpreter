"""Interpreter server

Starts the main interpreter web server. This initially creates a
Supervisor class object, loads all of the plugins from the ./plugins
folder, and hands them off to the Supervisor object for
server initialization.
"""
from os import environ

from src import supervisor


if __name__ == '__main__':
    try:
        PLUGIN_NAME = environ["PLUGIN"]
    except KeyError:
        print("Plugin not specified!")
        exit(99)

    SUPERVISOR = supervisor.SupervisorController(PLUGIN_NAME)

    try:
        SUPERVISOR.create_servers()
    except KeyError:
        exit(99)
    SUPERVISOR.spawn_servers()

    SUPERVISOR.monitor()
