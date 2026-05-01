import os, json

out = []
try:
    for pid in os.listdir('/proc'):
        if pid.isdigit():
            try:
                with open(f'/proc/{pid}/cmdline', 'rb') as f:
                    cmd_bytes = f.read()
                    if cmd_bytes:
                        cmd = cmd_bytes.replace(b'\0', b' ').decode('utf-8', 'replace')
                        if 'groupC50' in cmd or 'scripts/workflows' in cmd or '--enhancer-parallel' in cmd:
                            out.append({'pid': pid, 'cmd': cmd.strip()})
            except Exception as e:
                pass
except Exception as e:
    out.append({'error': str(e)})

with open('/tmp/find_pid.json', 'w') as f:
    json.dump(out, f, indent=2)
