"""Interpreter server

Starts the main interpreter web server. This initially creates a
Supervisor class object, loads all of the plugins from the ./plugins
folder, and hands them off to the Supervisor object for
server initialization.
"""
from os import environ, path

from src import supervisor


if __name__ == '__main__':
    """Entry point, creates Supervisor and begins process monitoring"""
    try:
        plugin_name = environ["PLUGIN"]
    except KeyError:
        print("Plugin not specified!")
        exit(99)

    supervisor_controller = supervisor.SupervisorController(plugin_name)

    try:
        supervisor_controller.create_servers()
    except KeyError:
        exit(99)
    supervisor_controller.spawn_servers()

    supervisor_controller.monitor()
