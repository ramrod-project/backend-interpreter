"""Unit testing for the linked_process module.
"""

from ctypes import c_bool
from multiprocessing import Pipe, Value
from pytest import raises

from src import linked_process

def test_linked_process_exceptions():
    """Test LinkedProcess class instantiation/exceptions.
    """

    with raises(KeyError):
        lp = linked_process.LinkedProcess()
    with raises(KeyError):
        lp = linked_process.LinkedProcess(name="test")
    s, _ = Pipe()
    with raises(KeyError):
        lp = linked_process.LinkedProcess(name="test", logger_pipe=s)
    with raises(TypeError):
        lp = linked_process.LinkedProcess(name="test", logger_pipe=s, target=None)
    def test():
        pass
    with raises(KeyError):
        lp = linked_process.LinkedProcess(name="test", logger_pipe=s, target=test)
    with raises(TypeError):
        lp = linked_process.LinkedProcess(name="test", logger_pipe=s, target=test, signal=False)
    sig = Value(c_bool, False)
    def test2(signal):
        while True:
            if signal.value:
                break
    lp = linked_process.LinkedProcess(name="test", logger_pipe=s, target=test2, signal=sig)
    try:
        lp.start()
    except Exception as ex:
        print(type(ex))
        assert type(ex) == TypeError

def test_linked_process_functionality():
    def test(logger_pipe, signal):
        while True:
            if signal.value:
                break
    sig = Value(c_bool, False)
    s, _ = Pipe()
    lp = linked_process.LinkedProcess(name="test", logger_pipe=s, target=test, signal=sig)
    lp.start()
    assert lp.is_alive() == True
    assert lp.restart() == True
    lp.terminate()
    assert lp.is_alive() == False