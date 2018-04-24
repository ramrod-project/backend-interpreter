"""Controller server

This is the main server file for the docker
interpreter controller.
"""
from os import path as ospath, getcwd
from time import sleep

import docker
CLIENT = docker.from_env()

if __name__ == "__main__":
    interpreter_path = ospath.join(
        "/".join(ospath.abspath(__file__).split("/")[:-2]),
        "plugin_interpreter"
    )

    CLIENT.networks.create("test")
    CLIENT.containers.run(
        "rethinkdb",
        name="rethinkdb",
        detach=True,
        ports={"28015/tcp": 28015},
        remove=True,
        network="test"
    )
    CLIENT.images.build(
        path=interpreter_path,
        tag="example-http/pcp",
        buildargs={
            "plugin": "ExampleHTTP",
            "stage": "PROD"
        }
    )
    CLIENT.containers.run(
        "example-http/pcp",
        name="plugin1",
        detach=True,
        network="test",
        ports={"8080/tcp": 8080},
        remove=True
    )
    
    containers = CLIENT.containers.list()
    print("Containers started, press <CTRL-C> to stop...")
    while True:
        try:
            sleep(1)
            pass
        except KeyboardInterrupt:
            print("\nKill signal received, stopping container(s)...")
            for container in containers:
                if container.name == "controller":
                    continue
                container.stop()
            sleep(1)
            print("Pruning networks...")
            CLIENT.networks.prune()
            exit(0)
