import subprocess

def get_id():
    output = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("ascii")
    return int(output[:8], 16)
