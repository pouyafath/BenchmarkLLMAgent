import os, json, subprocess

out = {}
try:
    cmd_out = subprocess.check_output(['ps', 'auxww']).decode('utf-8')
    out['ps'] = cmd_out
except Exception as e:
    out['error'] = str(e)

with open('/home/22pf2/.gemini/antigravity/brain/889e0434-bf7e-499d-85e1-b1ae721fbef5/ps_dump.json', 'w') as f:
    json.dump(out, f, indent=2)
