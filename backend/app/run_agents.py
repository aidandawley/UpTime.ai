import subprocess
import sys
import time

agents = [
    "app.agents.monitoring_agent",
    "app.agents.investigation_agent",
    "app.agents.patch_agent",
    "app.agents.github_agent",
    "app.agents.validation_agent",
]

processes = []

try:
    for agent in agents:
        print(f"Starting {agent}...")
        p = subprocess.Popen([sys.executable, "-m", agent])
        processes.append(p)
        time.sleep(1)

    print("All agents started.")

    for p in processes:
        p.wait()

except KeyboardInterrupt:
    print("Stopping agents...")

    for p in processes:
        p.terminate()

    time.sleep(2)

    for p in processes:
        if p.poll() is None:
            p.kill()