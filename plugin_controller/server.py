"""Controller server

This is the main server file for the docker
interpreter controller.

TODO:
"""
from os import environ
from signal import signal, SIGTERM
from time import sleep

from controller import Controller


HOST_PROTO = "TCP"
PLUGIN = "Harness"
try:
    if environ["STAGE"] == "PROD":
        NETWORK_NAME = "pcp"
        HOST_PORT = 5000
    else:
        NETWORK_NAME = "test"
        HOST_PORT = 5005
except KeyError:
    NETWORK_NAME = "test"
    HOST_PORT = 5005

try:
    TAG = environ["TRAVIS_BRANCH"].replace("master", "latest")
except KeyError:
    TAG = "latest"


def main(): # pragma: no cover
    """Main server entry point
    """
    plugin_controller = Controller(NETWORK_NAME, TAG)

    def sigterm_handler(_signo, _stack_frame):
        """Handles SIGTERM signal
        """
        plugin_controller.stop_all_containers()
        exit(0)

    signal(SIGTERM, sigterm_handler)

    if environ["STAGE"] == "DEV" and \
       not plugin_controller.dev_db():
        plugin_controller.log(
            40,
            "Port 28015 already allocated, \
            cannot launch rethinkdb container!"
        )
        exit(1)

    # Main control loop to be inserted below
    # Check state of running plugins (maintain map in local mem)
    # Update status of plugin in db
    # Check desired state in db
    # if current status =/= desired state, handle it

    plugin = plugin_controller.launch_plugin(
        PLUGIN,
        {HOST_PORT: HOST_PORT},
        HOST_PROTO
    )
    # Controller should do this automatically at some point.
    plugin_controller.container_mapping[PLUGIN] = plugin

    plugin_controller.log(
        20,
        "".join((PLUGIN, " started, press <CTRL-C> to stop..."))
    )
    while True:
        try:
            sleep(1)
        except KeyboardInterrupt:
            plugin_controller.stop_all_containers()
            exit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
