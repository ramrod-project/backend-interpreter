

import rethinkdb as r

def update_status_received(obj):
    conn = r.connect("127.0.0.1")
    obj['Status'] = "Waiting"
    print(r.db('Brain').table("Jobs").insert(obj, conflict="replace").run(conn))

def update_status_done(obj):
    conn = r.connect("127.0.0.1")
    obj['Status'] = "Done"
    print(r.db('Brain').table("Jobs").insert(obj, conflict="replace").run(conn))


