
content = {}


read_file_tt = """
Read File:

This command reads a file (requires full file path)
from the endpoint and returns the content of that file
to this host

Arguments:
1: Remote filename (string format)

Returns: The File itself

"""
delete_file_tt = """
Delete File:

This command Deletes a file from the endpoint

Arguments:
1: Remote filename (string format)

Returns: None

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

NOTE:
    Harness only support Binary files

    This will not work if the file is text

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
delete_regkey_tt = """
Delete Registry Key:

Deletes the Registry Key

Arguments:
1: Registry Key Location

Returns: Value Data
"""

list_devices_tt = """
List Connected Devices

Lists connected USB devices

Arguments:
None

Returns: Status code
"""
list_files_tt = """
List Files in a given directory


Arguments:
1: Directory Path
      MUST be a fully qualified path
          and it MUST be a directory

Returns:
File listing of the specified directory

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

terminate_tt = """
Terminate

Client closes itself with exit code 0

Arguments:
None

Returns:
None
"""

terminal_start_tt = """
Terminal Start

Begins telling this client to phone in more frequently

The client will change from it's default
call home to
checking in every one second


Arguments:
None

Returns:
None
"""

terminal_stop_tt = """
Terminal Stop

Client will return to checking in
at the default frequency

Arguments:
None

Returns:
None
"""

terminal_input_tt = """
Terminal Input

The "command" will be run in a shell
suitable for the host

On windows clients, expect the command to
run in a command shell (cmd.exe)

On posix clients, expect the command to
run in the users' default shell

Arguments:
1- the exact (escaped if required) command to run in a shell.

Returns:
The STDOUT of the shell
"""

command_templates = [
{
"CommandName":"get_file",
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
"CommandName":"delete_file",
"Tooltip":delete_file_tt,
"Output":False,
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
"CommandName":"put_file",
"Tooltip":write_file_tt,
"Output":True,
"Inputs":[
        {"Name":"SourceFilePath",
         "Type":"textbox",
         "Tooltip":"Must be uploaded here first",
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
"CommandName":"write_registry",
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
"CommandName":"read_registry",
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
"CommandName":"delete_registry",
"Tooltip":delete_regkey_tt,
"Output":True,
"Inputs":[
        {"Name":"KeyLocation",
         "Type":"textbox",
         "Tooltip":"HKLM is ok",
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
"CommandName":"list_files",
"Tooltip":list_files_tt,
"Output":True,
"Inputs":[
        {"Name":"DirectoryPath",
         "Type":"textbox",
         "Tooltip":"Must be fully qualified path and that path MUST be a directory",
         "Value":""
         },
         ],
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
        {"Name":"EchoString",
         "Type":"textbox",
         "Tooltip":"This string will be echoed back",
         "Value":""
         },
        ],
"OptionalInputs":[]
},
{
"CommandName":"terminate",
"Tooltip":terminate_tt,
"Output":False,
"Inputs":[],
"OptionalInputs":[]
},
{
"CommandName":"terminal_start",
"Tooltip":terminal_start_tt,
"Output":False,
"Inputs":[],
"OptionalInputs":[]
},
{
"CommandName":"terminal_stop",
"Tooltip":terminal_stop_tt,
"Output":False,
"Inputs":[],
"OptionalInputs":[]
},
{
"CommandName":"terminal_input",
"Tooltip":terminal_input_tt,
"Output":True,
"Inputs":[
         {"Name":"Command string",
         "Type":"textbox",
         "Tooltip":"This string will be executed on an appropriate command line",
         "Value":""
         },
         ],
"OptionalInputs":[]
},
]