"""Controller server

This is the main server file for the docker
interpreter controller.

TODO:
"""
import logging
from os import environ, getenv
from signal import signal, SIGTERM
from time import asctime, gmtime, sleep, time

from brain import r, connect, queries

from controller import Controller


logging.basicConfig(
    filename="logfile",
    filemode="a",
    format='%(date)s %(name)-12s %(levelname)-8s %(message)s'
)

LOGGER = logging.getLogger("controller")
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.DEBUG)

LOGLEVEL = getenv("LOGLEVEL", default="DEBUG")
if LOGLEVEL == "INFO":
    LOGGER.setLevel(logging.INFO)
elif LOGLEVEL == "WARNING":
    LOGGER.setLevel(logging.WARNING)
elif LOGLEVEL == "ERROR":
    LOGGER.setLevel(logging.ERROR)
elif LOGLEVEL == "CRITICAL":
    LOGGER.setLevel(logging.CRITICAL)


STAGE = getenv("STAGE", default="PROD")
if STAGE == "TESTING":
    RETHINK_HOST = "localhost"
    NETWORK_NAME = "test"
    HARNESS_PORT = 5005
elif STAGE == "DEV":
    RETHINK_HOST = "rethinkdb"
    NETWORK_NAME = "test"
    HARNESS_PORT = 5005
else:
    RETHINK_HOST = "rethinkdb"
    NETWORK_NAME = "pcp"
    HARNESS_PORT = 5000

HARNESS_PROTO = "TCP"
HARNESS_PLUGIN = "Harness"


MANIFEST_FILE = getenv("MANIFEST", default="./manifest.json")
START_HARNESS = getenv("START_HARNESS", default="NO")
TAG = getenv("TRAVIS_BRANCH", default="latest").replace("master", "latest")


PLUGIN_CONTROLLER = Controller(NETWORK_NAME, TAG)

# ---------------------------------------------------------
# --- Below are the acceptable state mappings for the   ---
# --- possible states for a plugin.                     ---
# ---------------------------------------------------------
AVAILABLE_MAPPING = {
    "Activate": PLUGIN_CONTROLLER.launch_plugin
}

ACTIVE_MAPPING = {
    "Stop": PLUGIN_CONTROLLER.stop_plugin,
    "Restart": PLUGIN_CONTROLLER.restart_plugin,
}

STOPPED_MAPPING = {
    "Activate": PLUGIN_CONTROLLER.launch_plugin,
    "Restart": PLUGIN_CONTROLLER.launch_plugin
}

# --- Not able to do anything right now, just wait      ---
# --- for restart.                                      ---
RESTARTING_MAPPING = {}

STATE_MAPPING = {
    "Available": AVAILABLE_MAPPING,
    "Active": ACTIVE_MAPPING,
    "Stopped": STOPPED_MAPPING,
    "Restarting": RESTARTING_MAPPING
}

# --- Maps docker container states to database entries  ---
STATUS_MAPPING = {
    "restarting": "Restarting",
    "running": "Active",
    "paused": "Stopped",
    "exited": "Stopped"
}
# ---------------------------------------------------------


def update_states():
    """Update the current states of the running
    containers.

    Queries the docker client to get the current
    states of the running plugin containers.
    """
    for name, _ in PLUGIN_CONTROLLER.container_mapping.items():
        # --- We have to update the container object here   ---
        # --- because the 'status' attribute is not updated ---
        # --- automatically.                                ---
        new_con = PLUGIN_CONTROLLER.get_container_from_name(name)
        PLUGIN_CONTROLLER.update_plugin({
            "Name": name,
            "State": STATUS_MAPPING[new_con.status]
        })
        PLUGIN_CONTROLLER.container_mapping[name] = new_con


def handle_state_change(plugin_data):
    """Handle a container state change

    When DesiredState and State are out of sync,
    this function is called on the plugin
    in question and the docker client attempts
    to modify the state.

    Arguments:
        plugin_data {dict} -- the plugin data as
        pulled from the database.

    Returns:
        {bool} -- True if success, False if failure.
    """ 
    current_state = STATE_MAPPING[plugin_data["State"]]
    desired_state = plugin_data["DesiredState"]
    success = False
    try:
        if current_state[desired_state](plugin_data):
            success = True
    except KeyError:
        to_log(
            "Invalid state transition! {} to {}".format(
                plugin_data["State"],
                desired_state
            ),
            40
        )
    plugin_data["DesiredState"] = ""
    to_log("plugin data: {}".format(plugin_data), 10)
    PLUGIN_CONTROLLER.update_plugin(plugin_data)
    return success


def check_states(cursor):
    """Check the current states in the database.

    Arguments:
        cursor {rethinkdb cursor} -- cursor containing
        the plugins and their statuses.
    """
    for plugin_data in cursor:
        actual = plugin_data["State"]
        desired = plugin_data["DesiredState"]
        if desired == "":
            continue
        if not handle_state_change(plugin_data):
            to_log(
                40,
                "State transition to {} from {} failed!".format(
                    desired,
                    actual
                )
            )


def to_log(log, level):
    """Send message to log

    Logs a message of a given level
    to the logger with a timestamp.

    Arguments:
        log {str} -- log message.
        level {int[10,20,30,40,50]} -- log level.
    """
    date = asctime(gmtime(time()))
    LOGGER.log(
        level,
        log,
        extra={ "date": date }
    )


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

    PLUGIN_CONTROLLER.load_plugins_from_manifest(MANIFEST_FILE)

    if START_HARNESS == "YES":
        port = "".join([
            str(HARNESS_PORT),
            "/",
            HARNESS_PROTO.lower()
        ])
        PLUGIN_CONTROLLER.launch_plugin({
            "Name": HARNESS_PLUGIN,
            "State": "Available",
            "DesiredState": "",
            "Interface": "",
            "ExternalPort": [port],
            "InternalPort": [port]
        })

    while True:
        # --- This main control loop monitors the running   ---
        # --- plugin containers. It takes the following     ---
        # --- actions:                                      ---
        # --- 1) Update the running plugin container states ---
        # --- 2) Query the plugin entries table             ---
        # --- 3) Check the DesiredState agains the State    ---
        # --- 3.1) If they differ, take appropriate action  ---
        try:
            update_states()
            cursor = queries.RPC.run(connect(host="rethinkdb"))
            check_states(cursor)
        except KeyboardInterrupt:
            PLUGIN_CONTROLLER.stop_all_containers()
            exit(0)
        sleep(1)


if __name__ == "__main__":  # pragma: no cover
    main()
