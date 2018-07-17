# Plugin Interpreter
[![Build Status](https://travis-ci.org/ramrod-project/backend-interpreter.svg?branch=dev)](https://travis-ci.org/ramrod-project/backend-interpreter)
[![Maintainability](https://api.codeclimate.com/v1/badges/72fa8fec9d9fe43497bd/maintainability)](https://codeclimate.com/github/ramrod-project/backend-interpreter/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/72fa8fec9d9fe43497bd/test_coverage)](https://codeclimate.com/github/ramrod-project/backend-interpreter/test_coverage)

## Guide

**Building interpreter image**

From top level repository:

`docker build -t ramrodpcp/interpreter-plugin:<tag> .`

**Running interpreter by itself in detached mode (development)**

Create network and start database.

```
$ docker network create test
$ docker run -d --rm --name rethinkdb --network test -p 28015:28015 -e "STAGE=DEV" -e "LOGLEVEL=DEBUG" ramrodpcp/datbase-brain:<dev,qa,latest>
```

Run the controller in the network you created.
```
$ docker run --rm --name controller --network test -ti -p <external_port>:<plugin_port> -e "STAGE=PROD" -e "LOGLEVEL=DEBUG" -e "PLUGIN=<plugin_name>" -e "PORT=<plugin_port>" ramrodpcp/interpreter-plugin:<tag>
```