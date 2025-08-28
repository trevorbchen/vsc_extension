import tempfile
import os

def read_file(path: str) -> str:
    with open(path, "r") as f:
        return f.read()

def save_temp_file(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".c")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return path
