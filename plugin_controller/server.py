"""This is the main server file for the docker
interpreter controller.
"""

import docker
CLIENT = docker.from_env()

if __name__ == '__main__':
    CLIENT.containers.run("gotest", detach=True, ports={"9090/tcp": 8080})
    print(CLIENT.containers.list())
