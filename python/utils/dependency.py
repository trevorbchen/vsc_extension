"""
Enhanced dependency resolution for C source files.
Handles include parsing, dependency classification, and safe code merging.
"""

import os
import re
import hashlib
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

@dataclass
class IncludeInfo:
    """Information about an include statement."""
    original_line: str
    filename: str
    is_system: bool  # True for <>, False for ""
    line_number: int

@dataclass
class DependencyNode:
    """Represents a dependency in the dependency graph."""
    filepath: str
    content: str
    includes: List[IncludeInfo]
    hash: str
    is_resolved: bool = False

class DependencyGraph:
    """Manages the dependency graph for C source files."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.nodes: Dict[str, DependencyNode] = {}
        self.resolved_cache: Dict[str, str] = {}
        
    def add_file(self, filepath: str) -> Optional[DependencyNode]:
        """Add a file to the dependency graph."""
        abs_path = self._resolve_path(filepath)
        if not abs_path or not abs_path.exists():
            return None
            
        # Use relative path as key for consistency
        rel_path = str(abs_path.relative_to(self.project_root))
        
        if rel_path in self.nodes:
            return self.nodes[rel_path]
        
        try:
            content = abs_path.read_text(encoding='utf-8')
        except (IOError, UnicodeDecodeError) as e:
            print(f"Warning: Could not read {abs_path}: {e}")
            return None
        
        includes = self._extract_includes(content)
        file_hash = hashlib.md5(content.encode()).hexdigest()
        
        node = DependencyNode(
            filepath=rel_path,
            content=content,
            includes=includes,
            hash=file_hash
        )
        
        self.nodes[rel_path] = node
        return node
    
    def _resolve_path(self, filepath: str) -> Optional[Path]:
        """Resolve a filepath to an absolute path within the project."""
        path = Path(filepath)
        
        if path.is_absolute():
            if not str(path).startswith(str(self.project_root)):
                return None  # Outside project
            return path
        
        # Try relative to project root first
        abs_path = self.project_root / path
        if abs_path.exists():
            return abs_path
        
        # Try as-is if it exists
        if path.exists():
            try:
                return path.resolve()
            except OSError:
                return None
        
        return None
    
    def _extract_includes(self, content: str) -> List[IncludeInfo]:
        """Extract include statements from C source code."""
        includes = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            # Match #include statements
            match = re.match(r'\s*#include\s*([<"])([^>"]+)[">]', line.strip())
            if match:
                bracket_type, filename = match.groups()
                includes.append(IncludeInfo(
                    original_line=line.strip(),
                    filename=filename,
                    is_system=(bracket_type == '<'),
                    line_number=i + 1
                ))
        
        return includes
    
    def resolve_dependencies(self, root_file: str) -> Dict[str, List[str]]:
        """
        Resolve all dependencies for a root file.
        Returns dict with 'internal' and 'external' dependency lists.
        """
        root_node = self.add_file(root_file)
        if not root_node:
            return {"internal": [], "external": []}
        
        internal = []
        external = []
        visited = set()
        
        def traverse(node: DependencyNode):
            if node.filepath in visited:
                return
            visited.add(node.filepath)
            
            for include in node.includes:
                if include.is_system:
                    # System include - add to external
                    if include.filename not in external:
                        external.append(include.filename)
                else:
                    # Local include - try to resolve
                    include_path = self._find_include_file(include.filename, node.filepath)
                    if include_path:
                        if include_path not in internal:
                            internal.append(include_path)
                        
                        # Recursively process this include
                        include_node = self.add_file(include_path)
                        if include_node:
                            traverse(include_node)
                    else:
                        # Could not resolve - treat as external
                        if include.filename not in external:
                            external.append(include.filename)
        
        traverse(root_node)
        
        # Remove the root file from internal dependencies
        if root_node.filepath in internal:
            internal.remove(root_node.filepath)
        
        return {"internal": internal, "external": external}
    
    def _find_include_file(self, filename: str, from_file: str) -> Optional[str]:
        """Find an include file relative to the including file."""
        from_dir = Path(from_file).parent
        
        # Search locations in order:
        search_paths = [
            self.project_root / from_dir / filename,  # Relative to including file
            self.project_root / filename,             # Relative to project root
        ]
        
        for path in search_paths:
            if path.exists():
                try:
                    return str(path.relative_to(self.project_root))
                except ValueError:
                    continue
        
        return None
    
    def get_merged_content(self, files: List[str], root_file: str) -> str:
        """
        Safely merge multiple C files into one compilation unit.
        Handles include guards and prevents duplicate definitions.
        """
        if not files:
            return ""
        
        merged_lines = []
        included_guards = set()
        defined_symbols = set()
        
        # Add standard header to prevent issues
        merged_lines.extend([
            "/* Merged source file generated by Formal Verifier */",
            "/* Original files: " + ", ".join(files) + " */",
            ""
        ])
        
        # Process each file
        for filepath in files:
            node = self.nodes.get(filepath)
            if not node:
                continue
            
            merged_lines.append(f"/* === Begin: {filepath} === */")
            
            # Process the file content
            processed_content = self._process_file_content(
                node.content, 
                filepath,
                included_guards,
                defined_symbols
            )
            
            merged_lines.extend(processed_content)
            merged_lines.append(f"/* === End: {filepath} === */")
            merged_lines.append("")
        
        # Add the root file content at the end
        root_node = self.nodes.get(root_file)
        if root_node:
            merged_lines.append(f"/* === Main source: {root_file} === */")
            processed_content = self._process_file_content(
                root_node.content,
                root_file,
                included_guards,
                defined_symbols,
                is_main=True
            )
            merged_lines.extend(processed_content)
        
        return "\n".join(merged_lines)
    
    def _process_file_content(self, content: str, filepath: str, 
                            included_guards: Set[str], defined_symbols: Set[str],
                            is_main: bool = False) -> List[str]:
        """Process individual file content for safe merging."""
        lines = content.split('\n')
        processed_lines = []
        skip_until_endif = 0
        current_guard = None
        
        for line in lines:
            stripped = line.strip()
            
            # Handle include guards
            if stripped.startswith('#ifndef') or stripped.startswith('#ifdef'):
                guard_match = re.search(r'#ifndef\s+(\w+)', stripped)
                if guard_match:
                    guard_name = guard_match.group(1)
                    if guard_name in included_guards:
                        skip_until_endif += 1
                        continue
                    current_guard = guard_name
            
            elif stripped.startswith('#define') and current_guard:
                define_match = re.search(r'#define\s+(\w+)', stripped)
                if define_match and define_match.group(1) == current_guard:
                    included_guards.add(current_guard)
                    defined_symbols.add(current_guard)
            
            elif stripped.startswith('#endif'):
                if skip_until_endif > 0:
                    skip_until_endif -= 1
                    continue
                current_guard = None
            
            elif stripped.startswith('#include'):
                if not is_main:  # Skip includes in header files being merged
                    continue
            
            if skip_until_endif == 0:
                processed_lines.append(line)
        
        return processed_lines

# Enhanced utility functions
def extract_includes(source_code: str) -> List[str]:
    """Extract include filenames from source code."""
    includes = re.findall(r'#include\s+[<"]([^">]+)[">]', source_code)
    return includes

def classify_dependencies(includes: List[str], project_root: str) -> Dict[str, List[str]]:
    """
    Classify dependencies into 'external' (system libs) and 'internal' (local project files).
    Enhanced version with better heuristics.
    """
    internal, external = [], []
    project_path = Path(project_root).resolve()
    
    for inc in includes:
        # System headers (definitive)
        if inc.startswith('/usr/') or inc.startswith('/opt/') or inc in [
            'stdio.h', 'stdlib.h', 'string.h', 'math.h', 'time.h', 'errno.h',
            'unistd.h', 'fcntl.h', 'sys/types.h', 'sys/stat.h', 'pthread.h'
        ]:
            external.append(inc)
            continue
        
        # Check if file exists in project
        potential_paths = [
            project_path / inc,
            project_path / 'include' / inc,
            project_path / 'src' / inc,
        ]
        
        found_locally = any(p.exists() for p in potential_paths)
        
        if found_locally:
            internal.append(inc)
        else:
            external.append(inc)
    
    return {"internal": internal, "external": external}

def resolve_internal_dependencies(internal_files: List[str], project_root: str) -> Dict[str, str]:
    """
    Enhanced version that properly resolves internal dependencies.
    """
    graph = DependencyGraph(project_root)
    resolved = {}
    
    for filename in internal_files:
        node = graph.add_file(filename)
        if node:
            resolved[filename] = node.content
    
    return resolved

def create_dependency_graph(root_file: str, project_root: str = ".") -> DependencyGraph:
    """Create a dependency graph starting from a root file."""
    graph = DependencyGraph(project_root)
    graph.add_file(root_file)
    return graph