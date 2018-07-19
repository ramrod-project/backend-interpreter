"""Unit testing for the linked_process module.
"""

from ctypes import c_bool
from multiprocessing import Pipe, Value
from pytest import fixture, raises

from src import linked_process


def test_linked_process_exceptions():
    """Test LinkedProcess class instantiation/exceptions.
    """

    with raises(KeyError):
        lp = linked_process.LinkedProcess()
    with raises(KeyError):
        lp = linked_process.LinkedProcess(name="test")
    with raises(KeyError):
        lp = linked_process.LinkedProcess(name="test")
    with raises(TypeError):
        lp = linked_process.LinkedProcess(name="test", target=None)
    def test():
        pass
    with raises(KeyError):
        lp = linked_process.LinkedProcess(name="test", target=test)
    with raises(TypeError):
        lp = linked_process.LinkedProcess(name="test", target=test, signal=False)
    sig = Value(c_bool, False)
    def test2(signal):
        while True:
            if signal.value:
                break
    with raises(TypeError):
        lp = linked_process.LinkedProcess(name="test", target=test2, signal=None)

def test_linked_process_functionality():
    def test(signal):
        while True:
            if signal.value:
                break
    sig = Value(c_bool, False)
    lp = linked_process.LinkedProcess(name="test", target=test, signal=sig)
    lp.start()
    assert lp.is_alive() == True
    assert lp.restart() == True
    lp.terminate()
    assert lp.is_alive() == False
