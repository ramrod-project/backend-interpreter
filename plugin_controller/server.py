"""Controller server

This is the main server file for the docker
interpreter controller.

TODO:
- update all functions to use new brain functions
- check database instead of local mem
"""
import logging
from os import environ, path as ospath
from random import randint
from signal import signal, SIGTERM
from sys import stderr
from time import asctime, gmtime, sleep, time

import docker
import brain


logging.basicConfig(
    filename="logfile",
    filemode="a",
    format='%(date)s %(name)-12s %(levelname)-8s %(message)s'
)
LOGGER = logging.getLogger("controller")
LOGGER.addHandler(logging.StreamHandler())

CLIENT = docker.from_env()
INTERPRETER_PATH = ospath.join(
    "/".join(ospath.abspath(__file__).split("/")[:-2]),
    "plugin_interpreter"
)
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


def set_logging(logger):
    """Set the logging level

    Set the python logging level for this process
    based on the "LOGLEVEL" env variable.
    """
    levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    try:
        logger.setLevel(levels[environ["LOGLEVEL"]])
    except KeyError:
        stderr.write("Invalid LOGLEVEL setting!\n")
        exit(1)


def create_plugin(plugin_data):
    """Creates a plugin in the 'Plugins' table of
    the 'Controller' database.
    
    Arguments:
        plugin_data {[type]} -- [description]
    """
    # brain.create_plugin_controller
    pass


def update_plugin_state(plugin_name, state):
    """Updates the plugin state to match the current
    state of its container.

    Takes a pluginn ame and current state.
    
    Arguments:
        plugin_name {string} -- plugin name.
        state {string} -- the current state of the
        plugin container ("Active", "Restarting",
        "Stopped").
    """
    # brain.update_plugin_state
    pass


def dev_db(ports):
    """Spins up db for dev environment

    When operating in a dev environment ("STAGE"
    environment variable is "DEV")

    Arguments:
        port_mapping {dict} -- a mapping for keeping
        track of used {host port: container}
        combinations.
    """
    if 28015 in ports:
        return False

    CLIENT.networks.prune()
    CLIENT.networks.create(NETWORK_NAME)

    rethink_container = CLIENT.containers.run(
        "".join(("ramrodpcp/database-brain:", TAG)),
        name="rethinkdb",
        detach=True,
        ports={"28015/tcp": 28015},
        network=NETWORK_NAME,
        remove=True
    )
    ports[28015] = rethink_container
    sleep(3)
    return True


def generate_port(ports):
    """Generate a random port for container

    Arguments:
        port_mapping {dict} -- a mapping for keeping
        track of used {host port: container}
        combinations.

    Returns:
        {int} -- the port to use for the docker
        container (internally).
    """
    rand_port = randint(1025, 65535)
    while rand_port in ports.keys():
        rand_port = randint(1025, 65535)
    return rand_port


def log(level, message):
    """Log a message

    Arguments:
        level {int} -- 10,20,30,40,50 are valid
        log levels.
        message {str} -- a string message to log.
    """
    LOGGER.log(
        level,
        message,
        extra={
            'date': asctime(gmtime(time()))
        }
    )


def launch_plugin(plugin, port, host_port, host_proto):
    """Launch a plugin container

    Arguments:
        plugin {str} -- name of the plugin to run.
        port {int} -- internal docker container port.
        host_port {int} -- port to use on the host.
        host_proto {str} -- TCP or UDP, the protocol used
        by the plugin.

    Returns:
        {Container} -- a Container object corresponding
        to the launched container.
    """
    if host_proto != "TCP" and host_proto != "UDP":
        raise TypeError
    if host_port > 65535:
        raise ValueError

    return CLIENT.containers.run(
        "".join(("ramrodpcp/interpreter-plugin:", TAG)),
        name=plugin,
        environment={
            "STAGE": environ["STAGE"],
            "LOGLEVEL": environ["LOGLEVEL"],
            "PLUGIN": plugin,
            "PORT": str(port)
        },
        detach=True,
        remove=True,
        network=NETWORK_NAME,
        ports={
            "".join([
                str(port),
                "/{}".format(HOST_PROTO.lower())
            ]): host_port
        }
    )


def restart_plugin(plugin_name):
    """Restart a plugin by name.
    
    Arguments:
        plugin_name {str} -- name of a plugin.
    """
    # get docker container and restart
    # update state in db
    # wait for timeout until restarted
    # return True if restarted else False
    pass


def stop_plugin(plugin_name):
    """Stop a plugin by name.
    
    Arguments:
        plugin_name {str} -- name of a plugin.
    """
    # get docker container and stop
    pass


def plugin_status(plugin_name):
    """Return the status of a plugin container
    
    Arguments:
        plugin_name {str} -- name of a plugin
    
    Returns:
        status {str} -- "Active", "Restarting", or "Stopped"
    """
    return status


def stop_all_containers(containers):
    """Clean up containers and network

    Stops all running containers and prunes
    the network (in dev environment).

    Arguments:
        containers {list} -- a list of all the containers
        ran by the container.
    """
    log(
        20,
        "Kill signal received, stopping container(s)..."
    )
    for container in containers:
        try:
            container.stop()
        except docker.errors.NotFound:
            log(
                20,
                "".join((container.name, " not found!"))
            )
            continue
    if environ["STAGE"] == "DEV":
        log(
            20,
            "Pruning networks..."
        )
        CLIENT.networks.prune()


def get_container_from_name(plugin_name):
    """Return a container object given a plugin name.
    
    Arguments:
        plugin_name {str} -- name of a plugin.

    Returns:
        con {container} -- a docker.container object corresponding
        to the plugin name.
    """
    return con


if __name__ == "__main__":  # pragma: no cover

    port_mapping = {}

    set_logging(LOGGER)

    def sigterm_handler(_signo, _stack_frame):
        """Handles SIGTERM signal
        """
        stop_all_containers(port_mapping.values())
        exit(0)

    signal(SIGTERM, sigterm_handler)

    if environ["STAGE"] == "DEV" and not dev_db(port_mapping):
        log(
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

    plugin_container = launch_plugin(
        PLUGIN,
        generate_port(port_mapping),
        HOST_PORT,
        HOST_PROTO
    )
    port_mapping[HOST_PORT] = plugin_container

    log(
        20,
        "Containers started, press <CTRL-C> to stop..."
    )
    while True:
        try:
            sleep(1)
        except KeyboardInterrupt:
            stop_all_containers(port_mapping.values())
            exit(0)
