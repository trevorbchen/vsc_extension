"""
Simple dependency resolution for C source files.
Handles basic include parsing and file merging.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Set

def extract_includes(source_code: str) -> List[str]:
    """Extract include filenames from C source code."""
    # Match both #include <file> and #include "file"
    pattern = r'#include\s*[<"]([^">]+)[">]'
    return re.findall(pattern, source_code)

def classify_includes(includes: List[str], project_root: str) -> Dict[str, List[str]]:
    """
    Classify includes into internal (project files) and external (system headers).
    """
    internal = []
    external = []
    project_path = Path(project_root)
    
    # Common system headers
    system_headers = {
        'stdio.h', 'stdlib.h', 'string.h', 'math.h', 'time.h', 'errno.h',
        'unistd.h', 'fcntl.h', 'sys/types.h', 'sys/stat.h', 'pthread.h',
        'ctype.h', 'assert.h', 'limits.h', 'float.h', 'stddef.h', 'stdint.h'
    }
    
    for include in includes:
        # Definitely system headers
        if include in system_headers or include.startswith('sys/'):
            external.append(include)
            continue
        
        # Look for the file in the project
        found = False
        for search_path in [project_path, project_path / 'include', project_path / 'src']:
            if (search_path / include).exists():
                internal.append(include)
                found = True
                break
        
        if not found:
            external.append(include)
    
    return {"internal": internal, "external": external}

def resolve_dependencies(source_code: str, file_path: str, project_root: str) -> List[str]:
    """
    Resolve internal dependencies for a source file.
    Returns list of internal header files to include.
    """
    includes = extract_includes(source_code)
    classified = classify_includes(includes, project_root)
    
    # Filter out files that don't exist or can't be read
    valid_internal = []
    project_path = Path(project_root)
    
    for include in classified["internal"]:
        # Try to find the file
        search_paths = [
            project_path / include,
            project_path / 'include' / include,
            project_path / 'src' / include,
            Path(file_path).parent / include  # Relative to source file
        ]
        
        for path in search_paths:
            if path.exists() and path.is_file():
                try:
                    # Test if we can read it
                    path.read_text(encoding='utf-8')
                    valid_internal.append(str(path))
                    break
                except (IOError, UnicodeDecodeError):
                    continue
    
    return valid_internal

def merge_source_files(main_source: str, dependency_files: List[str], project_root: str) -> str:
    """
    Merge main source with its dependencies.
    Simple concatenation with basic duplicate prevention.
    """
    if not dependency_files:
        return main_source
    
    merged_parts = []
    included_guards = set()
    
    # Add comment header
    merged_parts.append("/* Merged source file */")
    merged_parts.append("")
    
    # Process each dependency file
    for dep_file in dependency_files:
        try:
            content = Path(dep_file).read_text(encoding='utf-8')
            guard = extract_include_guard(content)
            
            # Skip if we've already included this guard
            if guard and guard in included_guards:
                continue
            
            if guard:
                included_guards.add(guard)
            
            # Remove #include statements from dependency files to avoid conflicts
            content = remove_includes(content)
            
            merged_parts.append(f"/* From: {os.path.basename(dep_file)} */")
            merged_parts.append(content)
            merged_parts.append("")
            
        except (IOError, UnicodeDecodeError) as e:
            merged_parts.append(f"/* Error reading {dep_file}: {e} */")
    
    # Add the main source
    merged_parts.append("/* Main source */")
    merged_parts.append(main_source)
    
    return "\n".join(merged_parts)

def extract_include_guard(content: str) -> str:
    """Extract include guard name from header content."""
    lines = content.split('\n')
    for line in lines[:10]:  # Check first 10 lines
        match = re.match(r'\s*#ifndef\s+(\w+)', line.strip())
        if match:
            return match.group(1)
    return None

def remove_includes(content: str) -> str:
    """Remove #include statements from content."""
    lines = content.split('\n')
    filtered_lines = []
    
    for line in lines:
        if not re.match(r'\s*#include\s+[<"]', line.strip()):
            filtered_lines.append(line)
    
    return '\n'.join(filtered_lines)

def get_project_files(project_root: str, extensions: List[str] = None) -> List[str]:
    """Get all C/H files in the project."""
    if extensions is None:
        extensions = ['.c', '.h']
    
    files = []
    project_path = Path(project_root)
    
    for ext in extensions:
        files.extend(project_path.rglob(f'*{ext}'))
    
    return [str(f) for f in files if f.is_file()]