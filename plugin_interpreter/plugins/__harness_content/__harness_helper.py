

import rethinkdb as r

def _perform_status_update(obj, new_status):
    conn = r.connect("127.0.0.1")
    obj['Status'] = new_status
    print(r.db('Brain').table("Jobs").insert(obj, conflict="replace").run(conn))

def update_status_received(obj):
    return _perform_status_update(obj, "Pending")

def update_status_done(obj):
    return _perform_status_update(obj, "Done")


