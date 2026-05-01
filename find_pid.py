import os, json

out = []
for pid in os.listdir('/proc'):
    if pid.isdigit():
        try:
            with open(f'/proc/{pid}/cmdline', 'rb') as f:
                cmd = f.read().replace(b'\0', b' ').decode('utf-8', 'replace')
                if 'run_groupC50' in cmd or 'python' in cmd:
                    out.append({'pid': pid, 'cmd': cmd.strip()})
        except:
            pass

with open('/home/22pf2/BenchmarkLLMAgent/find_pid.json', 'w') as f:
    json.dump(out, f, indent=2)
