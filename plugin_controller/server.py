"""Controller server

This is the main server file for the docker
interpreter controller.

TODO:
- handle multiple plugins/containers
- read config for plugin from file
- dynamic port assignment
- dynamic ip assignment
"""
import logging
from os import environ, path as ospath
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
if environ["STAGE"] == "DEV":
    NETWORK_NAME = "test"
else:
    NETWORK_NAME = "pcp"
try:
    TAG = environ["TRAVIS_BRANCH"]
except KeyError:
    TAG = "latest"
PLUGIN = "Harness"


def set_logging():

    logger.setLevel(logging.DEBUG)
    if environ["LOGLEVEL"] == "INFO":
        logger.setLevel(logging.INFO)
    elif environ["LOGLEVEL"] == "WARNING":
        logger.setLevel(logging.WARNING)
    elif environ["LOGLEVEL"] == "ERROR":
        logger.setLevel(logging.ERROR)
    elif environ["LOGLEVEL"] == "CRITICAL":
        logger.setLevel(logging.CRITICAL)


def dev_db():

    CLIENT.networks.create(NETWORK_NAME)

    CLIENT.containers.run(
        "".join(("ramrodpcp/database-brain:", TAG)),
        name="rethinkdb",
        detach=True,
        ports={"28015/tcp": 28015},
        network=NETWORK_NAME,
        remove=True
    )
    sleep(3)


def launch_container(plugin):
        
    CLIENT.containers.run(
        "".join(("ramrodpcp/interpreter-plugin:", TAG)),
        environment={
            "STAGE": environ["STAGE"],
            "LOGLEVEL": environ["LOGLEVEL"],
            "PLUGIN": plugin
        },
        detach=True,
        remove=True,
        network=NETWORK_NAME,
        ports={"5000/tcp": 5000,
               "5005/tcp": 5005}
    )


if __name__ == "__main__":

    set_logging()

    if environ["STAGE"] == "DEV":
        dev_db()

    launch_container(PLUGIN)
    
    containers = CLIENT.containers.list()
    logger.log(
        20,
        "Containers started, press <CTRL-C> to stop...",
        extra={
            'date': asctime(gmtime(time()))
        }
    )
    while True:
        try:
            sleep(1)
            pass
        except KeyboardInterrupt:
            logger.log(
                20,
                "Kill signal received, stopping container(s)...",
                extra={
                    'date': asctime(gmtime(time()))
                }
            )
            for container in containers:
                try:
                    if container.name == "controller":
                        continue
                    container.stop()
                except:
                    logger.log(
                        20,
                        "".join((container.name, " stopped or not running")),
                        extra={
                            'date': asctime(gmtime(time()))
                        }
                    )
                    continue
            if environ["STAGE"] == "DEV":
                logger.log(
                    20,
                    "Pruning networks...",
                    extra={ 
                        'date': asctime(gmtime(time()))
                    }
                )
                CLIENT.networks.prune()
            exit(0)
