"""Controller server

This is the main server file for the docker
interpreter controller.

TODO:
- handle multiple plugins/containers
- read config for plugin from file
- dynamic ip assignment
"""
import logging
from os import environ, path as ospath
from random import randint
from signal import signal, SIGTERM
from time import asctime, gmtime, sleep, time

import docker


logging.basicConfig(
    filename="logfile",
    filemode="a",
    format='%(date)s %(name)-12s %(levelname)-8s %(message)s'
)
logger = logging.getLogger("controller")
logger.addHandler(logging.StreamHandler())

CLIENT = docker.from_env()
INTERPRETER_PATH = ospath.join(
    "/".join(ospath.abspath(__file__).split("/")[:-2]),
    "plugin_interpreter"
)
HOST_PROTO = "TCP"
PLUGIN = "Harness"

if environ["STAGE"] == "DEV":
    NETWORK_NAME = "test"
    HOST_PORT = 5005
else:
    NETWORK_NAME = "pcp"
    HOST_PORT = 5000

try:
    TAG = environ["TRAVIS_BRANCH"].replace("master", "latest")
except KeyError:
    TAG = "latest"


def set_logging():
    """Set the logging level

    Set the python logging level for this process
    based on the "LOGLEVEL" env variable.
    """

    logger.setLevel(logging.DEBUG)
    if environ["LOGLEVEL"] == "INFO":
        logger.setLevel(logging.INFO)
    elif environ["LOGLEVEL"] == "WARNING":
        logger.setLevel(logging.WARNING)
    elif environ["LOGLEVEL"] == "ERROR":
        logger.setLevel(logging.ERROR)
    elif environ["LOGLEVEL"] == "CRITICAL":
        logger.setLevel(logging.CRITICAL)


def dev_db(port_mapping):
    """Spins up db for dev environment

    When operating in a dev environment ("STAGE"
    environment variable is "DEV")
    
    Arguments:
        port_mapping {dict} -- a mapping for keeping
        track of used {host port: container}
        combinations.
    """
    CLIENT.networks.create(NETWORK_NAME)

    rethink_container = CLIENT.containers.run(
        "".join(("ramrodpcp/database-brain:", TAG)),
        name="rethinkdb",
        detach=True,
        ports={"28015/tcp": 28015},
        network=NETWORK_NAME,
        remove=True
    )
    port_mapping[28015] = rethink_container
    sleep(3)

def generate_port(port_mapping):
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
    while rand_port not in port_mapping.keys():
        rand_port = randint(1025, 65535)
    return rand_port


def log(level, message):
    """Log a message
    
    Arguments:
        level {int} -- 10,20,30,40,50 are valid
        log levels.
        message {str} -- a string message to log.
    """
    logger.log(
        level,
        message,
        extra={
            'date': asctime(gmtime(time()))
        }
    )

def launch_container(plugin, port, host_port, host_proto):
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
    docker_string = "".join([
        str(port),
        "/{}".format(HOST_PROTO.lower())
    ])

    container = CLIENT.containers.run(
        "".join(("ramrodpcp/interpreter-plugin:", TAG)),
        name="".join((
            plugin,
            "-{}_{}".format(host_port, host_proto)
        )),
        environment={
            "STAGE": environ["STAGE"],
            "LOGLEVEL": environ["LOGLEVEL"],
            "PLUGIN": plugin,
            "PORT": port
        },
        detach=True,
        remove=True,
        network=NETWORK_NAME,
        ports={docker_string: host_port}
    )
    return container


def teardown(containers):
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
            if container.name == "controller":
                continue
            container.stop()
        except:
            log(
                20,
                "".join((container.name, " stopped or not running"))
            )
            continue
    if environ["STAGE"] == "DEV":
        log(
            20,
            "Pruning networks..."
        )
        CLIENT.networks.prune()


if __name__ == "__main__":  # pragma: no cover

    port_mapping = {}

    def sigterm_handler(_signo, _stack_frame):
        teardown(port_mapping.values())
        exit(0)

    signal(SIGTERM, sigterm_handler)

    set_logging()

    if environ["STAGE"] == "DEV":
        dev_db(port_mapping)

    plugin_container = launch_container(PLUGIN, generate_port(port_mapping), HOST_PORT, HOST_PROTO)
    port_mapping[HOST_PORT] = plugin_container

    log(
        20,
        "Containers started, press <CTRL-C> to stop..."
    )
    while True:
        try:
            sleep(1)
        except KeyboardInterrupt:
            teardown(port_mapping.values())
            exit(0)
