# meant to parse dependencies such as functions imported from other files
import os
import re
from typing import List, Dict

def extract_includes(source_code: str) -> List[str]:
    """
    Parse C-style include statements (#include).
    Returns list of included headers or files.
    """
    includes = re.findall(r'#include\s+[<"]([^">]+)[">]', source_code)
    return includes

def classify_dependencies(includes: List[str], project_root: str) -> Dict[str, List[str]]:
    """
    Classify dependencies into 'external' (system libs) and 'internal' (local project files).
    
    Assumes:
      - External = standard headers like <stdio.h>
      - Internal = relative project files like "myutils.h"
    """
    internal, external = [], []

    for inc in includes:
        if inc.endswith(".h") and os.path.exists(os.path.join(project_root, inc)):
            internal.append(inc)
        else:
            external.append(inc)

    return {"internal": internal, "external": external}

def resolve_internal_dependencies(internal_files: List[str], project_root: str) -> Dict[str, str]:
    """
    Load internal dependency files so their code can be included in verification.
    Returns a mapping: filename -> file content
    """
    resolved = {}
    for f in internal_files:
        path = os.path.join(project_root, f)
        if os.path.exists(path):
            with open(path, "r") as fp:
                resolved[f] = fp.read()
    return resolved
