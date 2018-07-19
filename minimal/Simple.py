"""
very simple plugin
controller_plugin.py should be in your path!
"""

import controller_plugin
from ctypes import c_bool, windll
from time import sleep


class Simple(controller_plugin.ControllerPlugin):
    def __init__(self, ):
        name = "Simple"
        functionality = CMDS  # example below
        super().__init__(name, functionality)

    def _start(self, logger, ext_signal):
        #################################################################################################\n",
        # Add Plugin specific startup routine here\n",
        pass
        pass
        handle = windll.kernel32
        pass
        pass
        ################################################################################################\n",
        # Add plugin control loop here",
        # most basic: loop the request_job function, operate on it, return output back
        # does not need to be synchronous, but is here for simplicity



        while not ext_signal.value:
            new_job = self.request_job()  # <dict> or None
            if new_job != None: #None means there is no job for you
                output_content = str(windll.kernel32.GetModuleHandleA) #  do some work with the job
                self.respond_output(new_job, output_content)
            sleep(3)



        ###############################################################################################\n",
        # Put cleanup code here"
        pass
        pass
        pass
        pass
        ###############################################################################################\n",

    def _stop(self):
        exit(0)


CMDS = [{"CommandName" : "help",
         "Tooltip" : "Let's do 'get help'",
         "Output" : True,
         "Inputs" : [{"Name" : "argument1",
                      "Type" : "textbox",
                      "Tooltip" : "if value is set to 'ok', it will get help",
                      "Value" : "default is not ok"}]}]


if __name__ == "__main__":
    S = Simple()
    ext_signal = c_bool(False)
    S.start(None, ext_signal)
