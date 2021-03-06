"""Interpreter server

Starts the main interpreter web server. This initially creates a
Supervisor class object, loads all of the plugins from the ./plugins
folder, and hands them off to the Supervisor object for
server initialization.
"""
from os import environ, name as osname, path as ospath
from pkgutil import iter_modules

from plugins import *


try:
    PLUGIN_NAME = environ["PLUGIN"]
except KeyError:
    print("Plugin not specified!")
    exit(99)


def get_class_instance(plugin_name):
    """Returns class instances from 'plugins' folder.

    Returns:
        list -- List containing class instances of all plugins.
    """
    path = "".join((
        ospath.dirname(ospath.abspath(__file__)),
        "/plugins"
    ))
    modules = iter_modules(path=[path])

    for _, mod_name, _ in modules:
        if mod_name == plugin_name:
            loaded_mod = __import__("plugins." + mod_name, fromlist=[mod_name])
            loaded_class = getattr(loaded_mod, plugin_name)
            return loaded_class()
    return None


def main():  # pragma: no cover
    """Main server entry point
    """
    plugin_instance = get_class_instance(PLUGIN_NAME)

    # Start process as main thread with dummy signal
    try:
        plugin_instance.start()
    except KeyboardInterrupt:
        plugin_instance.stop()

if __name__ == '__main__':  # pragma: no cover
    main()
