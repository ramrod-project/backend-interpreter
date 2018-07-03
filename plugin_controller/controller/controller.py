"""Controller

This is the controller module.

TODO:
- Maintain local mapping of plugin names to containers.
- Use local mapping as cache and update as needed
"""
import logging
from os import environ, path as ospath
from random import randint
import re
from requests import ReadTimeout
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

CLIENT = docker.from_env()
CONTAINERS_EXCEPTED = [
    "database",
    "backend",
    "websockets",
    "frontend"
]
LOGLEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}


class Controller():


    def __init__(self, network_name, tag):
        self.logger = logging.getLogger("controller")
        self.logger.setLevel(environ.get("LOGLEVEL", "DEBUG"))
        self.logger.addHandler(logging.StreamHandler())
        self.container_mapping = {}
        self.network_name = network_name
        self.tag = tag

    def _check_db_errors(self, response):
        if response["errors"] > 0:
            self.log(
                40,
                response["first_error"]
            )
            return False
        return True

    def create_plugin(self, plugin_data):
        """Creates a plugin in the 'Plugins' table of
        the 'Controller' database. plugin_data should contain
        the following:

        {
            Name<str>,
            State<str> [default: "Available"],
            DesiredState<str> [default: ""],
            Interface<str(IP) [default: ""],
            ExternalPort<str>,
            InternalPort<str>
        }
        
        Arguments:
            plugin_data {dict} -- data for plugin
        """
        if plugin_data["Name"] == "":
            return self._check_db_errors({
                "errors": 1,
                "first_error": "Plugin must be given a valid name!"
            })
        result = brain.queries.create_plugin_controller(plugin_data)
        return self._check_db_errors(result)

    def _create_port(self, port_data):
        """Creates a port entry in the 'Ports' table of
        the 'Controller' database. port_data should contain
        the following:

        {
            InterfaceName<str> [default: "All"],
            Address<str(IP) [default: ""],
            TCPPorts<list<str> >,
            UDPPorts<list<str> >
        }
        
        Arguments:
            port_data {dict} -- data for port
        """
        result = brain.queries.create_port_controller(port_data)
        return self._check_db_errors(result)

    def update_plugin(self, plugin_data):
        """Updates the plugin info to match the current
        state of its container.

        Takes plugin data and current state.
        
        Arguments:
            plugin_data {dict} -- data for plugin.
        """
        result = brain.queries.update_plugin_controller(plugin_data)
        return self._check_db_errors(result)

    def dev_db(self):
        """Spins up db for dev environment

        When operating in a dev environment ("STAGE"
        environment variable is "DEV")

        Arguments:
            port_mapping {dict} -- a mapping for keeping
            track of used {host port: container}
            combinations.
        """

        CLIENT.networks.prune()
        CLIENT.networks.create("test")
        try:
            self.container_mapping["rethinkdb"] = \
                CLIENT.containers.run(
                    "".join(("ramrodpcp/database-brain:", self.tag)),
                    name="rethinkdb",
                    detach=True,
                    ports={"28015/tcp": 28015},
                    network=self.network_name,
                    remove=True
                )
        except brain.r.ReqlError:
            return False
        sleep(3)
        return True

    def log(self, level, message):
        """Log a message

        Arguments:
            level {int} -- 10,20,30,40,50 are valid
            log levels.
            message {str} -- a string message to log.
        """
        self.logger.log(
            level,
            message,
            extra={
                'date': asctime(gmtime(time()))
            }
        )

    def launch_plugin(self, plugin, ports, host_proto):
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

        external_ports = []
        internal_ports = []
        ports_config = {}
        port_data = {
            "InterfaceName": "",
            "Address": "",
            "TCPPorts": [],
            "UDPPorts": []
        }

        for container_port, host_port in ports.items():
            if container_port > 65535 or host_port > 65535:
                raise ValueError
            external_ports.append(str(host_port))
            internal_ports.append(str(container_port))
            ports_config["".join([
                str(container_port),
                "/",
                host_proto.lower()
            ])] = str(host_port)
            if host_proto == "TCP":
                port_data["TCPPorts"].append(str(host_port))
            else:
                port_data["UDPPorts"].append(str(host_port))

        plugin_data = {
            "Name": plugin,
            "State": "Available",
            "DesiredState": "",
            "Interface": "",
            "ExternalPorts": external_ports,
            "InternalPorts": internal_ports
        }

        existing = self.get_container_from_name(plugin)
        if self.restart_plugin(plugin_data):
            return existing

        self.create_plugin(plugin_data)

        self._create_port(port_data)

        # ---Right now only one port mapping per plugin is supported---
        # ---hence the internal_ports[0].                           ---
        con = CLIENT.containers.run(
            "".join(("ramrodpcp/interpreter-plugin:", self.tag)),
            name=plugin,
            environment={
                "STAGE": environ["STAGE"],
                "LOGLEVEL": environ["LOGLEVEL"],
                "PLUGIN": plugin,
                "PORT": internal_ports[0]
            },
            detach=True,
            network=self.network_name,
            ports=ports_config
        )
        if self.wait_for_plugin(plugin_data):
            return con
        return None

    def wait_for_plugin(self, plugin_data):
        """Wait for container to start
        
        Arguments:
            plugin_data {dict} -- plugin data
        
        Raises:
            docker.errors.ContainerError -- if container
            not found, raise error.
        
        Returns:
            {bool} -- True - container running,
            False - container not running after 10 seconds
        """
        now = time()
        status = None
        while time() - now < 10:
            con = self.get_container_from_name(plugin_data["Name"])
            if not con:
                raise docker.errors.ContainerError
            status = con.status
            if status == "running":
                plugin_data["State"] = "Active"
                plugin_data["DesiredState"] = ""
                self.update_plugin(plugin_data)
                return True
            sleep(1)
        return False

    def restart_plugin(self, plugin_data):
        """Restart a plugin by name.
        
        Arguments:
            plugin_data {dict} -- plugin data

        Returns:
            {bool} -- True: restarted False: not restarted
        """
        con = self.get_container_from_name(plugin_data["Name"])
        if not con:
            return False
        if con.status == "running":
            return True
        con.restart()
        plugin_data["State"] = "Restarting"
        self.update_plugin(plugin_data)
        return self.wait_for_plugin(plugin_data)

    def stop_plugin(self, plugin_data):
        """Stop a plugin by name.
        
        Arguments:
            plugin_data {dict} -- plugin data

        Returns:
            {bool} -- True: stopped False: not stopped
        """
        con = self.get_container_from_name(plugin_data["Name"])
        if con:
            con.stop()
            try:
                con.wait(timeout=5)
                plugin_data["State"] = "Stopped"
                self.update_plugin(plugin_data)
                return True
            except ReadTimeout as ex:
                self.log(
                    40,
                    str(ex)
                )
        return False

    def plugin_status(self, plugin_data):
        """Return the status of a plugin container
        
        Arguments:
            plugin_data {dict} -- plugin data
        
        Returns:
            {str} -- "Active", "Restarting", or "Stopped"
        """
        result = brain.queries.get_plugin_by_name_controller(
            plugin_data["Name"]
        )
        if len(result) == 1:
            return result[0]["State"]
        return None


    def get_all_containers(self):
        """Return all plugin containers

        Returns:
            containers {list} -- list of plugins
            containers.
        """
        pattern = re.compile('|'.join(
            [''.join(['.*?', c, '.*?']) for c in CONTAINERS_EXCEPTED]
        ))
        containers = []
        for con in CLIENT.containers.list():
            match = pattern.match(con.name)
            if not match:
                containers.append(con)
        return containers

    def stop_all_containers(self):
        """Clean up containers and network

        Stops all running containers and prunes
        the network (in dev environment).

        Arguments:
            containers {list} -- a list of all the containers
            ran by the container.
        """
        self.log(
            20,
            "Kill signal received, stopping container(s)..."
        )
        for container in self.get_all_containers():
            try:
                container.stop()
            except docker.errors.NotFound:
                self.log(
                    20,
                    "".join((container.name, " not found!"))
                )
                continue
        if environ["STAGE"] == "DEV":
            self.log(
                20,
                "Pruning networks..."
            )
            CLIENT.networks.prune()

    def get_container_from_name(self, plugin_name):
        """Return a container object given a plugin name.
        
        Arguments:
            plugin_name {str} -- name of a plugin.

        Returns:
            con {container} -- a docker.container object corresponding
            to the plugin name.
        """
        for container in self.get_all_containers():
            if container.name == plugin_name:
                return container
        self.log(
            20,
            "".join((plugin_name, " not found!"))
        )
        return None
