"""Controller server

This is the main server file for the docker
interpreter controller.

TODO:
"""
from os import environ
from signal import signal, SIGTERM
from time import sleep

from brain import r, connect, queries

from controller import Controller


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

HARNESS_PROTO = "TCP"
HARNESS_PLUGIN = "Harness"

try:
    START_HARNESS = environ["START_HARNESS"]
except:
    START_HARNESS = "NO"

try:
    TAG = environ["TRAVIS_BRANCH"].replace("master", "latest")
except KeyError:
    TAG = "latest"


PLUGIN_CONTROLLER = Controller(NETWORK_NAME, TAG)

"""Below are the acceptable state mappings for the
possible states for a plugin.
"""
AVAILABLE_MAPPING = {
    "Activate": PLUGIN_CONTROLLER.launch_plugin
}

ACTIVE_MAPPING = {
    "Activate": PLUGIN_CONTROLLER.stop_plugin,
    "Restart": PLUGIN_CONTROLLER.restart_plugin,
}

STOPPED_MAPPING = {
    "Activate": PLUGIN_CONTROLLER.launch_plugin,
    "Restart": PLUGIN_CONTROLLER.launch_plugin
}

# Not able to do anything right now, just wait for restart
RESTARTING_MAPPING = {}

STATE_MAPPING = {
    "Available": AVAILABLE_MAPPING,
    "Active": ACTIVE_MAPPING,
    "Stopped": STOPPED_MAPPING,
    "Restarting": RESTARTING_MAPPING
}


def handle_state_change(plugin_data):
    current_state = STATE_MAPPING[plugin_data["State"]]
    desired_state = plugin_data["DesiredState"]
    try:
        current_state[desired_state](plugin_data)
        return True
    except KeyError:
        print("Invalid state transition!")
        # log
        plugin_data["DesiredState"] = ""
        PLUGIN_CONTROLLER.update_plugin(plugin_data)

def check_states(cursor):
    for plugin_data in cursor:
        if plugin_data["DesiredState"] == "":
            continue
        handle_state_change(plugin_data)


def main():  # pragma: no cover
    """Main server entry point
    """
    PLUGIN_CONTROLLER = Controller(NETWORK_NAME, TAG)

    def sigterm_handler(_signo, _stack_frame):
        """Handles SIGTERM signal
        """
        PLUGIN_CONTROLLER.stop_all_containers()
        exit(0)

    signal(SIGTERM, sigterm_handler)

    if (environ["STAGE"] == "DEV" or 
        environ["STAGE"] == "QA") and \
       not PLUGIN_CONTROLLER.dev_db():
        PLUGIN_CONTROLLER.log(
            40,
            "Port 28015 already allocated, \
            cannot launch rethinkdb container!"
        )
        exit(1)

    PLUGIN_CONTROLLER.load_plugins_from_manifest("./manifest.json")

    if START_HARNESS == "YES":
        PLUGIN_CONTROLLER.launch_plugin(
            HARNESS_PLUGIN,
            {HOST_PORT: HOST_PORT},
            HARNESS_PROTO
        )

    # Main control loop to be inserted below
    # Check state of running plugins (maintain map in local mem)
    # Update status of plugin in db
    # Check desired state in db
    # if current status =/= desired state, handle it

    while True:
        try:
            sleep(1)
            cursor = queries.RPC.run(connect(host="rethinkdb"))

        except KeyboardInterrupt:
            PLUGIN_CONTROLLER.stop_all_containers()
            exit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
