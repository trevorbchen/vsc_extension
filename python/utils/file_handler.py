import tempfile
import os
from pathlib import Path

def read_file(path: str) -> str:
    """Read file content with error handling."""
    try:
        with open(path, "r", encoding='utf-8') as f:
            return f.read()
    except (IOError, UnicodeDecodeError) as e:
        raise Exception(f"Could not read file {path}: {e}")

def save_temp_file(content: str, suffix: str = ".c") -> str:
    """Save content to a temporary file."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "w", encoding='utf-8') as f:
            f.write(content)
        return path
    except Exception as e:
        os.close(fd)
        if os.path.exists(path):
            os.remove(path)
        raise Exception(f"Could not save temp file: {e}")

def file_exists(path: str) -> bool:
    """Check if file exists and is readable."""
    return Path(path).exists() and Path(path).is_file()

def get_file_size(path: str) -> int:
    """Get file size in bytes."""
    return Path(path).stat().st_size if file_exists(path) else 0