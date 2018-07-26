import requests
from time import sleep
MAX_REQUEST_TIMEOUT = 120
HARNESS_STR = "127.0.0.1:"


def control_loop(client_info, port=5000):
  client = client_info
  looping = True
  # loop through, GET from server and then act on the command
  while looping:
    try:
      resp = requests.get("http://{}{}/harness/{}".format(HARNESS_STR, str(port), client), timeout=MAX_REQUEST_TIMEOUT)
      cmd, args = resp.text.split(",",1)
      handle_resp(cmd, args, client)
    except ConnectionError:
      continue

def handle_resp(resp, args, client):
  print(resp)
  if "terminate" in resp:
    SystemExit()
  elif "echo" in resp:
    requests.post("http://{}/response/{}".format(HARNESS_STR, client), data={"data": args}, timeout=MAX_REQUEST_TIMEOUT)
  elif "sleep" in resp:
    sleep(5)
  elif "list_files" in resp:
    requests.post("http://{}/response/{}".format(HARNESS_STR, client), data={"data": "data.txt\nresponse.exe\n"})
  elif "put_file":
    requests.get("http://{}/givemethat/{}/{}".format(HARNESS_STR, client, args), timeout=MAX_REQUEST_TIMEOUT)
  elif "get_file":
    pass
  elif "read_registry":
    pass
  elif "delete_registry":
    pass
  elif "write_registry":
    pass
  elif "create_process":
    pass
  elif "terminate_process":
    pass
  elif "delete_file":
    pass

if __name__ == "__main__":
  client_info = "C_127.0.0.1_1"
  control_loop(client_info)
