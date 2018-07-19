from minimal.Simple import self_test, Simple
from time import sleep
from ctypes import c_bool
from multiprocessing import Pool
from brain.queries import RBO, RBJ
from brain import connect
EXT_SIGNAL = c_bool(False)


def notest_signal_sleeper(ext_signal):
    sleep(9)


def notest_back_in_main(result):
    global EXT_SIGNAL
    EXT_SIGNAL.value = True
    print("Set to done")


def test_minimal_jobs():
    with Pool(processes=2) as pool:
        sleep(1)
        pool.apply_async(notest_signal_sleeper,
                         (EXT_SIGNAL,),
                         callback=notest_back_in_main)
        self_test(EXT_SIGNAL)
    c = connect()
    jobs = 0
    for job in RBJ.run(c):
        jobs += 1
        assert job["Status"] == "Done"
    assert jobs > 0
    outputs = 0
    for output in RBO.run(c):
        outputs += 1
        assert output["Content"][0] == "<"
    assert outputs > 0


if __name__ == "__main__":
    test_minimal_jobs()
