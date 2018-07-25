import requests
from time import sleep
MAX_REQUEST_TIMEOUT = 120



def control_loop(client_info):
  client = client_info
  looping = True
  # loop through, GET from server and then act on the command
  while looping:
    resp = requests.get("http://127.0.0.1:5000/harness/{}".format(client), timeout=MAX_REQUEST_TIMEOUT)
    handle_resp(resp.text, client)

def handle_resp(resp, client):
  if "terminate" in resp:
    SystemExit()
  elif "echo" in resp:
    requests.post("http://127.0.0.1:5000/response/{}".format(client), data={"data": resp}, timeout=MAX_REQUEST_TIMEOUT)
  elif "sleep" in resp:
    sleep(5)
  elif "list_files" in resp:
    requests.post("http://127.0.0.1:5000/response/{}".format(client), data={"data": "data.txt\nresponse.exe\n"})
  elif "put_file":
    requests.get("http://127.0.0.1:5000/givemethat/{}/filename.txt".format(client), timeout=MAX_REQUEST_TIMEOUT)
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
