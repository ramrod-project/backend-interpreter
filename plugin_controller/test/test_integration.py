from multiprocessing import Process
from time import sleep, time

import brain
import docker
from pytest import fixture, raises

from ..controller import *
from .. import server
from test_controller import brain_conn, clear_dbs, controller, env, rethink

CLIENT = docker.from_env()

def test_make_available(brain_conn, clear_dbs, controller, env, rethink):
    """Test automatic creation of plugin entry
    in the Controller.Plugins table.
    """
    pass


def test_available_to_start(brain_conn, clear_dbs, controller, env, rethink):
    """Test starting a plugin which is already in
    the database as 'Available'.
    """
    pass

def test_start_to_restart(brain_conn, clear_dbs, controller, env, rethink):
    """Test starting a plugin which is already in
    the database as 'Available'.
    """
    pass