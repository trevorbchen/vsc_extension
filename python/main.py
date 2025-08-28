#!/usr/bin/env python3
"""
Enhanced main entry point for the formal verifier backend.
Supports multiple output formats and better integration with the VS Code extension.
"""

import sys
import os
import json
import argparse
import time
from typing import Optional

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(__file__))

from utils.file_handler import read_file
from enhanced_pipeline import run_pipeline_with_progress, PipelineProgress, VerificationPipeline
from config_manager import get_config_manager, apply_env_overrides
from ui.results import format_results

def setup_argument_parser():
    """Setup command line argument parsing."""
    parser = argparse.ArgumentParser(
        description='Formal Verification Backend for VS Code Extension',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s main.c                    # Basic verification
  %(prog)s main.c --json             # JSON output for VS Code
  %(prog)s main.c --progress         # Show progress updates
  %(prog)s --config                  # Show current configuration
  %(prog)s --test                    # Run self-tests
        """
    )
    
    parser.add_argument('file', nargs='?', help='C source file to verify')
    parser.add_argument('--json', action='store_true', 
                       help='Output results in JSON format for VS Code integration')
    parser.add_argument('--progress', action='store_true',
                       help='Show progress updates during verification')
    parser.add_argument('--config', action='store_true',
                       help='Show current configuration and exit')
    parser.add_argument('--test', action='store_true',
                       help='Run self-tests and exit')
    parser.add_argument('--project-root', type=str,
                       help='Override project root directory')
    parser.add_argument('--preserve-temps', action='store_true',
                       help='Preserve temporary files for debugging')
    parser.add_argument('--no-deps', action='store_true',
                       help='Skip dependency resolution')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    return parser

def progress_callback(progress: PipelineProgress):
    """Callback function for progress updates."""
    percentage = progress.completion_percentage
    stage = progress.current_stage.value
    elapsed = progress.elapsed_time
    
    # Output progress in a format VS Code can parse
    print(f"Progress: {percentage:.0f}%")
    print(f"Stage: {stage}")
    print(f"Elapsed: {elapsed:.1f}s")
    
    if progress.warnings:
        for warning in progress.warnings:
            print(f"Warning: {warning}")
    
    sys.stdout.flush()

def show_configuration():
    """Display current configuration."""
    config_manager = get_config_manager()
    config = apply_env_overrides(config_manager.get_config())
    
    print("Current Configuration:")
    print("=" * 40)
    print(f"Config file: {config_manager.config_path}")
    print()
    
    print("API Settings:")
    print(f"  Annotator URL: {config.api.annotator_url}")
    print(f"  Verifier URL:  {config.api.verifier_url}")
    print(f"  Timeout:       {config.api.timeout}s")
    print(f"  Auth Token:    {'Set' if config.api.auth_token else 'Not set'}")
    print()
    
    print("Verification Settings:")
    print(f"  Inline Dependencies:    {config.verification.inline_dependencies}")
    print(f"  Preserve Temp Files:    {config.verification.preserve_temp_files}")
    print(f"  Max File Size:          {config.verification.max_file_size} bytes")
    print(f"  Supported Extensions:   {', '.join(config.verification.supported_extensions)}")
    print()
    
    print("UI Settings:")
    print(f"  Show Progress:          {config.ui.show_progress}")
    print(f"  Auto Save Before Verify: {config.ui.auto_save_before_verify}")
    print(f"  Result Display Mode:    {config.ui.result_display_mode}")
    print()
    
    if config.project_root:
        print(f"Project Root: {config.project_root}")
        print()
    
    # Validate configuration
    errors = config_manager.validate_config()
    if errors:
        print("Configuration Errors:")
        for key, error in errors.items():
            print(f"  {key}: {error}")
    else:
        print("✅ Configuration is valid")

def run_self_tests():
    """Run self-tests to verify the system is working."""
    try:
        # Import and run tests
        from test_suite import run_tests
        
        print("Running self-tests...")
        result = run_tests()
        
        success = len(result.failures) == 0 and len(result.errors) == 0
        return success
        
    except ImportError:
        print("Self-tests not available (test_suite.py not found)")
        return False
    except Exception as e:
        print(f"Error running self-tests: {e}")
        return False

def format_json_output(result, elapsed_time: float):
    """Format output as JSON for VS Code consumption."""
    if result.success and result.verification_result:
        output = {
            "success": True,
            "verification": result.verification_result,
            "elapsed_time": elapsed_time,
            "temp_files": result.temp_files,
            "stages_completed": [stage.value for stage in result.progress.stages_completed]
        }
        
        if result.progress.warnings:
            output["warnings"] = result.progress.warnings
    else:
        output = {
            "success": False,
            "errors": result.progress.errors if result.progress else ["Unknown error"],
            "elapsed_time": elapsed_time
        }
    
    return json.dumps(output, indent=2)

def main():
    """Main entry point."""
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    # Handle special commands
    if args.config:
        show_configuration()
        return 0
    
    if args.test:
        success = run_self_tests()
        return 0 if success else 1
    
    # Validate required arguments
    if not args.file:
        print("Error: No input file specified", file=sys.stderr)
        parser.print_help()
        return 1
    
    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' does not exist", file=sys.stderr)
        return 1
    
    # Setup logging level
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Read source file
        if not args.json:
            print(f"Reading source file: {args.file}")
        
        source_code = read_file(args.file)
        
        # Determine project root
        project_root = args.project_root or os.path.dirname(os.path.abspath(args.file))
        
        # Setup progress callback if requested
        progress_cb = progress_callback if args.progress and not args.json else None
        
        # Apply configuration overrides
        config_manager = get_config_manager()
        config = config_manager.get_config()
        
        if args.preserve_temps:
            config.verification.preserve_temp_files = True
        
        if args.no_deps:
            config.verification.inline_dependencies = False
        
        if args.project_root:
            config.project_root = args.project_root
        
        # Apply environment variable overrides
        config = apply_env_overrides(config)
        
        # Run verification pipeline
        start_time = time.time()
        
        if not args.json:
            print("Starting formal verification pipeline...")
            print("-" * 40)
        
        result = run_pipeline_with_progress(
            source_code=source_code,
            file_path=args.file,
            project_root=project_root,
            progress_callback=progress_cb
        )
        
        elapsed_time = time.time() - start_time
        
        # Output results
        if args.json:
            # JSON output for VS Code
            print("VERIFICATION_RESULTS_START")
            print(format_json_output(result, elapsed_time))
            print("VERIFICATION_RESULTS_END")
        else:
            # Human-readable output
            print("-" * 40)
            
            if result.success and result.verification_result:
                formatted_result = format_results(result.verification_result)
                print(formatted_result)
            else:
                print("❌ Verification pipeline failed:")
                for error in result.progress.errors:
                    print(f"  - {error}")
            
            print(f"\nCompleted in {elapsed_time:.2f} seconds")
            
            if result.temp_files:
                print(f"\nTemporary files:")
                for temp_file in result.temp_files:
                    print(f"  - {temp_file}")
        
        # Return appropriate exit code
        if result.success:
            if result.verification_result and result.verification_result.get("verified", False):
                return 0  # Verification successful
            else:
                return 2  # Verification failed (but pipeline succeeded)
        else:
            return 1  # Pipeline failed
        
    except KeyboardInterrupt:
        print("\nVerification interrupted by user", file=sys.stderr)
        return 130
    
    except Exception as e:
        if args.json:
            error_output = {
                "success": False,
                "errors": [f"Unexpected error: {str(e)}"],
                "elapsed_time": 0
            }
            print("VERIFICATION_RESULTS_START")
            print(json.dumps(error_output, indent=2))
            print("VERIFICATION_RESULTS_END")
        else:
            print(f"Error: {e}", file=sys.stderr)
            if args.verbose:
                import traceback
                traceback.print_exc()
        
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)