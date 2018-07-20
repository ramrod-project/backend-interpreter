"""
very simple plugin
controller_plugin.py should be in your path!
"""

import controller_plugin
from ctypes import c_bool
from time import sleep
from os import environ


class Simple(controller_plugin.ControllerPlugin):
    def __init__(self, ):
        name = "Simple"
        functionality = [CMD]  # example below
        super().__init__(name, functionality)

    def _start(self, logger, ext_signal):
        # #####################################################################
        # Add Plugin specific startup routine here\n",
        pass
        pass
        handle = None  # or a pointer to a DLL
        pass
        pass
        # #####################################################################
        # Add plugin control loop here",
        # most basic: loop the request_job function,
        # operate on it,
        # return output back
        # does not need to be synchronous, but is here for simplicity

        while not ext_signal.value:
            new_job = self.request_job()  # <dict> or None
            if new_job is not None:  # None means there is no job for you
                # do some work with the job
                output_content = "<"  # call your handle to DLL here
                self.respond_output(new_job, output_content)
            sleep(1)

        # #####################################################################
        # Put cleanup code here"
        pass
        pass
        pass
        pass
        # #####################################################################

    def _stop(self):
        exit(0)


CMD = {"CommandName": "help",
       "Tooltip": "Let's do 'get help'",
       "Output": True,
       "Inputs": [{"Name": "argument1",
                   "Type": "textbox",
                   "Tooltip": "if value is set to 'ok', it will get help",
                   "Value": "default is not ok"}]}
TGT = {
    "PluginName": "Simple",
    "Location": "127.0.0.1",
    "Port": "0000",
    "Optional": {"anything": "anything"}
}

JOBS = [{"JobTarget": TGT,
         "Status": "Ready",
         "StartTime": 0,
         "JobCommand": CMD}]


def self_test(ext_signal=None):
    if ext_signal is None:
        ext_signal = c_bool(False)
    from brain.queries.writes import insert_jobs
    assert insert_jobs(JOBS)["inserted"] == 1
    S = Simple()
    S.start(None, ext_signal)


if __name__ == "__main__":
    self_test()
