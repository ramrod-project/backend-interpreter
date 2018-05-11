"""Controller server

This is the main server file for the docker
interpreter controller.

TODO:
- multiple plugin names
- get port/protocol requirement from plugin
"""
import logging
from os import environ, path as ospath
from time import asctime, gmtime, sleep, time

logging.basicConfig(
    filename="logfile",
    filemode="a",
    format='%(date)s %(name)-12s %(levelname)-8s %(message)s'
)

logger = logging.getLogger("controller")
logger.addHandler(logging.StreamHandler())

import docker
CLIENT = docker.from_env()

if __name__ == "__main__":

    logger.setLevel(logging.DEBUG)
    if environ["LOGLEVEL"] == "INFO":
        logger.setLevel(logging.INFO)
    elif environ["LOGLEVEL"] == "WARNING":
        logger.setLevel(logging.WARNING)
    elif environ["LOGLEVEL"] == "ERROR":
        logger.setLevel(logging.ERROR)
    elif environ["LOGLEVEL"] == "CRITICAL":
        logger.setLevel(logging.CRITICAL)

    interpreter_path = ospath.join(
        "/".join(ospath.abspath(__file__).split("/")[:-2]),
        "plugin_interpreter"
    )

    tag = ":latest"

    CLIENT.networks.create("test")
    if environ["STAGE"] == "DEV":
        CLIENT.containers.run(
            "ramrodpcp/database-brain:latest",
            name="rethinkdb",
            detach=True,
            ports={"28015/tcp": 28015},
            remove=True,
            network="test"
        )
        tag = ":dev"
    CLIENT.containers.run(
        "ramrodpcp/interpreter-plugin" + tag,
        name="plugin1",
        environment={
            "STAGE": environ["STAGE"],
            "LOGLEVEL": environ["LOGLEVEL"],
            "PLUGIN": "ExampleHTTP"
        },
        detach=True,
        network="test",
        ports={"8080/tcp": 8080},
        remove=True
    )
    
    containers = CLIENT.containers.list()
    logger.log(
        20,
        "Containers started, press <CTRL-C> to stop...",
        extra={ 'date': asctime(gmtime(time()))
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
                extra={ 'date': asctime(gmtime(time()))
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
                        container.name + " stopped or not running",
                        extra={ 'date': asctime(gmtime(time()))
                        }
                    )
                    continue
            logger.log(
                20,
                "Pruning networks...",
                extra={ 'date': asctime(gmtime(time()))
                }
            )
            CLIENT.networks.prune()
            exit(0)
