"""Controller server

This is the main server file for the docker
interpreter controller.

TODO:
"""
import logging
from os import environ
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

LOGLEVEL = environ["LOGLEVEL"]
if LOGLEVEL == "INFO":
    LOGGER.setLevel(logging.INFO)
elif LOGLEVEL == "WARNING":
    LOGGER.setLevel(logging.WARNING)
elif LOGLEVEL == "ERROR":
    LOGGER.setLevel(logging.ERROR)
elif LOGLEVEL == "CRITICAL":
    LOGGER.setLevel(logging.CRITICAL)


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
    "Stop": PLUGIN_CONTROLLER.stop_plugin,
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

STATUS_MAPPING = {
    "restarting": "Restarting",
    "running": "Active",
    "paused": "Stopped",
    "exited": "Stopped"
}


def update_states():

    for name, _ in PLUGIN_CONTROLLER.container_mapping:
        # ---We have to update the container object here    ---
        # ---because the 'status' attribute is not updated  ---
        # ---automatically.                                 ---
        new_con = PLUGIN_CONTROLLER.get_container_from_name(name)
        PLUGIN_CONTROLLER.update_plugin({
            "Name": name,
            "State": STATE_MAPPING[new_con.status]
        })
        PLUGIN_CONTROLLER.container_mapping[name] = new_con


def to_log(log, level):
    
    date = asctime(gmtime(time()))
    LOGGER.log(
        level,
        log,
        extra={ "date": date }
    )


def handle_state_change(plugin_data):

    current_state = STATE_MAPPING[plugin_data["State"]]
    desired_state = plugin_data["DesiredState"]
    try:
        if current_state[desired_state](plugin_data):
            return True
    except KeyError:
        to_log("Invalid state transition!", 40)
    plugin_data["DesiredState"] = ""
    PLUGIN_CONTROLLER.update_plugin(plugin_data)
    return False


def check_states(cursor):

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

    while True:
        try:
            sleep(1)
            update_states()
            cursor = queries.RPC.run(connect(host="rethinkdb"))
            check_states(cursor)
        except KeyboardInterrupt:
            PLUGIN_CONTROLLER.stop_all_containers()
            exit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
