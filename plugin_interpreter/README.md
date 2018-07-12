In order to create a plugin you must create a python script with the name of
the the plugin. Inside this script you must create a class with the name of
the plugin file's name inside of the plugins folder.

ExamplePlugin.py
```python
from ..src import controller_plugin

class ExamplePlugin(controller_plugin.ControllerPlugin):
```

You will need to specify the capabilities of your plugin to the database.
you can do this either by creating a list of dictionaries containing each
command inside the plugin file and passing it to the super's constructor,
```python
commands = [
  {
    "CommandName": "my command",
    "Tooltip": "A helpful tooltip.",
    "Output": True,
    "Inputs": [
      {
        "Name": "task",
        "Type": "textbox",
        "Tooltip": "type the option you want"
        "Value": ""
      }
    ],
    "OptionalInputs":[
      {
        "Name": "bonus field",
        "Type": "textbox",
        "Tooltip": "type the optional option you want"
        "Value": ""
      }
    ]
  }
]
def __init__(self):
  super().__init__("ExamplePlugin", commands)
```
or you can place the commands in JSON format in a .json file with the same
name as the plugin in the plugins folder and not pass a command list to the
super's constructor.

```python
"CommandName"
```
The name of the command.
```python
"Tooltip"
```
An explanation of the command.
```python
"Output"
```
Whether or not the command will have output. Uses a boolean value
```python
"Inputs"
```
A list of inputs required to execute the command. This list can be empty
```python
"OptionalInputs"
```
A list of inputs not required to execute the command. This list can be empty
An Input has the following:
```python
"Name"
```
A name for the input
```python
"Type"
```
What kind of ui element should be created for this input
```python
"Tooltip"
```
An explanation for the input
```python
"Value"
```
An empty field where the input will have its value stored. Can be filled to
create a default value.

```python
def __init__(self):
  super().__init__("ExamplePlugin")
```

you **must** also override 2 functions, start() and _stop()
```python
def start(self, logger, signal):

def _stop(self):
```
start() is the entrypoint of the plugin. It should have some sort of
control loop or lead to one. You will be given a logger to log any issues
and a ctype boolean `signal` that can be used to know when the plugin is
being shut down by the controller. `signal.value` will be true if the plugin is
to be shut down. _stop() is used for any cleanup or teardown you may need and
is called when the plugin ends.

A typical plugin will interact with 2 main Controller_Plugin methods:
```python
self.request_job()
self.respond_output()
```
`request_job()` will return the next job and automatically update its state
in the databse.
`respond_output(job, output)` takes a job and the output associated with it and
update the database with it as well as update the job's state.

If you need to signify that an error has occured in plugin operation you can use
`respond_error(job[, message])` where you specify the job that errored and an
optional error message. This will update the job's status to error.

`get_file(filename)` can be used if you want to get a file uploaded by a user
from the database.

Normally the state of a job is managed automatically by `request_job()` and 
`respond_output()`, but If you need to alter the status of a job you can use
`update_job_status(job, status)` to set the state of a job. Note you are only
allowed to use the following as states:
* "Ready"
* "Pending"
* "Done"
* "Error"

`update_job(job)` can be called to easily transition from Ready to Pending
or from Pending to Done.

`get_job_id(job)` and `get_job_command(job)` can be used to grab the id or
command from a job as strings
