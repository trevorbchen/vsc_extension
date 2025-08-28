"""
Simple, robust verification pipeline for C programs.
Handles basic dependency resolution, annotation, and verification.
"""

import os
import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

# Import our modules
from api.annotator import annotate_code
from api.verifier import verify_code
from utils.file_handler import save_temp_file, read_file
from utils.dependency import resolve_dependencies, merge_source_files
from ui.results import format_results
from config_manager import get_config

class Stage(Enum):
    """Pipeline stages."""
    INIT = "Initialization"
    DEPENDENCIES = "Resolving Dependencies"
    MERGE = "Merging Code"
    ANNOTATE = "Adding Annotations"
    VERIFY = "Formal Verification"
    COMPLETE = "Complete"

@dataclass
class Result:
    """Pipeline result."""
    success: bool
    verification_result: Optional[Dict[str, Any]] = None
    errors: List[str] = None
    merged_code: Optional[str] = None
    temp_files: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.temp_files is None:
            self.temp_files = []

class Pipeline:
    """Simple verification pipeline."""
    
    def __init__(self, project_root: str = ".", progress_callback=None):
        self.project_root = project_root
        self.progress_callback = progress_callback
        self.config = get_config()
        self.logger = self._setup_logger()
    
    def _setup_logger(self):
        """Setup basic logging."""
        logger = logging.getLogger('pipeline')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(levelname)s: %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def _report_progress(self, stage: Stage, message: str = ""):
        """Report progress to callback if provided."""
        if self.progress_callback:
            self.progress_callback(stage, message)
        if message:
            self.logger.info(f"{stage.value}: {message}")
    
    def run(self, source_code: str, file_path: Optional[str] = None) -> Result:
        """Run the complete verification pipeline."""
        result = Result(success=False)
        
        try:
            # Stage 1: Initialize and validate
            self._report_progress(Stage.INIT, "Validating input")
            if not source_code or not source_code.strip():
                result.errors.append("Source code is empty")
                return result
            
            if len(source_code) > self.config.verification.max_file_size:
                result.errors.append(f"File too large (>{self.config.verification.max_file_size} bytes)")
                return result
            
            # Stage 2: Resolve dependencies
            self._report_progress(Stage.DEPENDENCIES)
            if file_path and self.config.verification.inline_dependencies:
                internal_deps = resolve_dependencies(source_code, file_path, self.project_root)
            else:
                internal_deps = []
            
            # Stage 3: Merge code with dependencies
            self._report_progress(Stage.MERGE)
            if internal_deps:
                merged_code = merge_source_files(source_code, internal_deps, self.project_root)
                result.merged_code = merged_code
                self.logger.info(f"Merged {len(internal_deps)} dependencies")
            else:
                merged_code = source_code
                result.merged_code = merged_code
            
            # Stage 4: Add annotations
            self._report_progress(Stage.ANNOTATE)
            annotated_code = annotate_code(merged_code)
            
            # Save temp file if needed
            if self.config.verification.preserve_temp_files:
                temp_file = save_temp_file(annotated_code, suffix=".annotated.c")
                result.temp_files.append(temp_file)
                self.logger.info(f"Saved annotated code: {temp_file}")
            
            # Stage 5: Verify
            self._report_progress(Stage.VERIFY)
            verification_result = verify_code(annotated_code)
            result.verification_result = verification_result
            
            self._report_progress(Stage.COMPLETE)
            result.success = True
            
            # Log final result
            if verification_result.get("verified", False):
                self.logger.info("✅ Verification successful")
            else:
                error_count = len(verification_result.get("errors", []))
                self.logger.warning(f"❌ Verification failed with {error_count} errors")
            
        except Exception as e:
            error_msg = f"Pipeline failed: {str(e)}"
            result.errors.append(error_msg)
            self.logger.error(error_msg)
        
        return result

def run_pipeline(source_code: str, project_root: str = ".") -> str:
    """Simple function interface for backward compatibility."""
    pipeline = Pipeline(project_root)
    result = pipeline.run(source_code)
    
    if result.success and result.verification_result:
        return format_results(result.verification_result)
    else:
        return f"❌ Pipeline failed: {'; '.join(result.errors)}"

def run_pipeline_with_progress(source_code: str, file_path: Optional[str] = None,
                              project_root: str = ".", progress_callback=None) -> Result:
    """Run pipeline with progress tracking."""
    pipeline = Pipeline(project_root, progress_callback)
    return pipeline.run(source_code, file_path)