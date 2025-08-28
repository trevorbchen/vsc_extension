"""
Enhanced verification pipeline with proper error handling, logging, and progress tracking.
"""

import os
import time
import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

# Import our enhanced modules
from api.annotator import annotate_code
from api.verifier import verify_code
from utils.file_handler import save_temp_file
from utils.enhanced_dependency import DependencyGraph, classify_dependencies
from ui.results import format_results
from config_manager import get_config

class PipelineStage(Enum):
    """Pipeline execution stages."""
    INIT = "initialization"
    DEPENDENCY_RESOLUTION = "dependency_resolution" 
    CODE_MERGING = "code_merging"
    ANNOTATION = "annotation"
    VERIFICATION = "verification"
    RESULT_FORMATTING = "result_formatting"
    COMPLETE = "complete"

@dataclass
class PipelineProgress:
    """Tracks pipeline execution progress."""
    current_stage: PipelineStage = PipelineStage.INIT
    stages_completed: List[PipelineStage] = field(default_factory=list)
    total_stages: int = len(PipelineStage) - 1  # Exclude COMPLETE
    start_time: float = field(default_factory=time.time)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def completion_percentage(self) -> float:
        return (len(self.stages_completed) / self.total_stages) * 100
    
    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time

@dataclass 
class PipelineResult:
    """Complete pipeline execution result."""
    success: bool
    verification_result: Optional[Dict[str, Any]] = None
    progress: Optional[PipelineProgress] = None
    temp_files: List[str] = field(default_factory=list)
    merged_code: Optional[str] = None
    annotated_code: Optional[str] = None

class PipelineError(Exception):
    """Custom exception for pipeline errors."""
    def __init__(self, message: str, stage: PipelineStage, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.stage = stage
        self.original_error = original_error

class VerificationPipeline:
    """Enhanced verification pipeline with robust error handling and progress tracking."""
    
    def __init__(self, project_root: str = ".", progress_callback: Optional[Callable[[PipelineProgress], None]] = None):
        self.project_root = project_root
        self.progress_callback = progress_callback
        self.config = get_config()
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Setup logging for the pipeline."""
        logger = logging.getLogger('verification_pipeline')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def _update_progress(self, progress: PipelineProgress, stage: PipelineStage, 
                        message: Optional[str] = None):
        """Update pipeline progress and notify callback."""
        progress.current_stage = stage
        
        if message:
            self.logger.info(f"{stage.value}: {message}")
        
        if self.progress_callback:
            self.progress_callback(progress)
    
    def _validate_input(self, source_code: str, file_path: Optional[str] = None) -> None:
        """Validate input parameters."""
        if not source_code or not source_code.strip():
            raise PipelineError("Source code is empty or None", PipelineStage.INIT)
        
        if len(source_code) > self.config.verification.max_file_size:
            raise PipelineError(
                f"Source code exceeds maximum size of {self.config.verification.max_file_size} bytes",
                PipelineStage.INIT
            )
        
        if file_path:
            ext = os.path.splitext(file_path)[1]
            if ext not in self.config.verification.supported_extensions:
                raise PipelineError(
                    f"Unsupported file extension: {ext}",
                    PipelineStage.INIT
                )
    
    def run_pipeline(self, source_code: str, file_path: Optional[str] = None) -> PipelineResult:
        """
        Run the complete verification pipeline with enhanced error handling.
        
        Args:
            source_code: The C source code to verify
            file_path: Optional path to the source file for better dependency resolution
            
        Returns:
            PipelineResult with verification results and metadata
        """
        progress = PipelineProgress()
        result = PipelineResult(success=False, progress=progress, temp_files=[])
        
        try:
            # Stage 1: Initialization and validation
            self._update_progress(progress, PipelineStage.INIT, "Validating input")
            self._validate_input(source_code, file_path)
            progress.stages_completed.append(PipelineStage.INIT)
            
            # Stage 2: Dependency resolution
            self._update_progress(progress, PipelineStage.DEPENDENCY_RESOLUTION, 
                                "Resolving dependencies")
            internal_files, external_deps = self._resolve_dependencies(source_code, file_path)
            progress.stages_completed.append(PipelineStage.DEPENDENCY_RESOLUTION)
            
            # Stage 3: Code merging
            self._update_progress(progress, PipelineStage.CODE_MERGING, "Merging source files")
            merged_code = self._merge_code(source_code, internal_files, file_path)
            result.merged_code = merged_code
            progress.stages_completed.append(PipelineStage.CODE_MERGING)
            
            # Stage 4: Annotation
            self._update_progress(progress, PipelineStage.ANNOTATION, "Adding ACSL annotations")
            annotated_code = self._annotate_code(merged_code)
            result.annotated_code = annotated_code
            progress.stages_completed.append(PipelineStage.ANNOTATION)
            
            # Save annotated code to temp file if configured
            if self.config.verification.preserve_temp_files or True:  # Always save for debugging
                temp_file = save_temp_file(annotated_code)
                result.temp_files.append(temp_file)
                self.logger.info(f"Annotated code saved to: {temp_file}")
            
            # Stage 5: Verification
            self._update_progress(progress, PipelineStage.VERIFICATION, "Running formal verification")
            verification_result = self._verify_code(annotated_code)
            result.verification_result = verification_result
            progress.stages_completed.append(PipelineStage.VERIFICATION)
            
            # Stage 6: Result formatting
            self._update_progress(progress, PipelineStage.RESULT_FORMATTING, "Formatting results")
            progress.stages_completed.append(PipelineStage.RESULT_FORMATTING)
            
            progress.current_stage = PipelineStage.COMPLETE
            result.success = True
            
            self.logger.info(f"Pipeline completed successfully in {progress.elapsed_time:.2f}s")
            
        except PipelineError as e:
            self.logger.error(f"Pipeline failed at {e.stage.value}: {e}")
            progress.errors.append(str(e))
            if e.original_error:
                self.logger.error(f"Original error: {e.original_error}")
        except Exception as e:
            self.logger.error(f"Unexpected error in pipeline: {e}")
            progress.errors.append(f"Unexpected error: {str(e)}")
        
        return result
    
    def _resolve_dependencies(self, source_code: str, file_path: Optional[str]) -> tuple:
        """Resolve and classify dependencies."""
        try:
            if file_path and self.config.verification.inline_dependencies:
                # Use enhanced dependency graph
                graph = DependencyGraph(self.project_root)
                deps = graph.resolve_dependencies(file_path)
                internal_files = deps["internal"]
                external_deps = deps["external"]
            else:
                # Fallback to simple classification
                import re
                includes = re.findall(r'#include\s+[<"]([^">]+)[">]', source_code)
                classified = classify_dependencies(includes, self.project_root)
                internal_files = classified["internal"]
                external_deps = classified["external"]
            
            self.logger.info(f"Found {len(internal_files)} internal and {len(external_deps)} external dependencies")
            return internal_files, external_deps
            
        except Exception as e:
            raise PipelineError(
                f"Failed to resolve dependencies: {str(e)}", 
                PipelineStage.DEPENDENCY_RESOLUTION,
                e
            )
    
    def _merge_code(self, source_code: str, internal_files: List[str], file_path: Optional[str]) -> str:
        """Merge source code with internal dependencies."""
        try:
            if not internal_files or not self.config.verification.inline_dependencies:
                return source_code
            
            if file_path:
                # Use enhanced merging with dependency graph
                graph = DependencyGraph(self.project_root)
                graph.add_file(file_path)
                merged_code = graph.get_merged_content(internal_files, file_path)
            else:
                # Fallback to simple concatenation
                combined_code = ""
                for filename in internal_files:
                    filepath = os.path.join(self.project_root, filename)
                    if os.path.exists(filepath):
                        with open(filepath, 'r') as f:
                            content = f.read()
                        combined_code += f"\n/* Inlined from {filename} */\n{content}\n"
                
                merged_code = combined_code + f"\n/* Original source */\n{source_code}"
            
            self.logger.info(f"Merged code size: {len(merged_code)} characters")
            return merged_code
            
        except Exception as e:
            raise PipelineError(
                f"Failed to merge code: {str(e)}",
                PipelineStage.CODE_MERGING,
                e
            )
    
    def _annotate_code(self, code: str) -> str:
        """Add ACSL annotations to the code."""
        try:
            # Call annotation API with timeout
            annotated = annotate_code(code)
            self.logger.info(f"Code annotation completed, added {len(annotated) - len(code)} characters")
            return annotated
            
        except Exception as e:
            raise PipelineError(
                f"Failed to annotate code: {str(e)}",
                PipelineStage.ANNOTATION,
                e
            )
    
    def _verify_code(self, annotated_code: str) -> Dict[str, Any]:
        """Run formal verification on the annotated code."""
        try:
            verification_result = verify_code(annotated_code)
            
            if verification_result.get("verified", False):
                self.logger.info("Verification successful")
            else:
                error_count = len(verification_result.get("errors", []))
                self.logger.warning(f"Verification failed with {error_count} errors")
            
            return verification_result
            
        except Exception as e:
            raise PipelineError(
                f"Failed to verify code: {str(e)}",
                PipelineStage.VERIFICATION,
                e
            )
    
    def cleanup_temp_files(self, result: PipelineResult) -> None:
        """Clean up temporary files if not configured to preserve them."""
        if not self.config.verification.preserve_temp_files:
            for temp_file in result.temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        self.logger.debug(f"Cleaned up temp file: {temp_file}")
                except Exception as e:
                    self.logger.warning(f"Failed to clean up {temp_file}: {e}")

# Convenience function for backward compatibility
def run_pipeline(source_code: str, project_root: str = ".") -> str:
    """
    Run the verification pipeline and return formatted results.
    This maintains backward compatibility with the original API.
    """
    pipeline = VerificationPipeline(project_root)
    result = pipeline.run_pipeline(source_code)
    
    if result.success and result.verification_result:
        return format_results(result.verification_result)
    else:
        error_msg = "; ".join(result.progress.errors) if result.progress else "Unknown error"
        return f"❌ Pipeline failed: {error_msg}"

# Enhanced pipeline with progress tracking
def run_pipeline_with_progress(source_code: str, file_path: Optional[str] = None,
                              project_root: str = ".", 
                              progress_callback: Optional[Callable[[PipelineProgress], None]] = None) -> PipelineResult:
    """
    Run the verification pipeline with progress tracking.
    
    Args:
        source_code: The C source code to verify
        file_path: Optional path to the source file
        project_root: Root directory of the project
        progress_callback: Optional callback to receive progress updates
        
    Returns:
        Complete pipeline result with all metadata
    """
    pipeline = VerificationPipeline(project_root, progress_callback)
    result = pipeline.run_pipeline(source_code, file_path)
    
    # Clean up temp files if needed
    pipeline.cleanup_temp_files(result)
    
    return result