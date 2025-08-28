#!/usr/bin/env python3
"""
Simple main entry point for the formal verifier backend.
Handles command line interface and VS Code integration.
"""

import sys
import os
import json
import argparse
import time

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from utils.file_handler import read_file
from pipeline import run_pipeline_with_progress, Stage
from config_manager import get_config_manager, apply_env_overrides
from ui.results import format_results

def setup_args():
    """Setup command line arguments."""
    parser = argparse.ArgumentParser(
        description='Formal Verification Backend',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('file', nargs='?', help='C source file to verify')
    parser.add_argument('--json', action='store_true', 
                       help='Output JSON for VS Code integration')
    parser.add_argument('--progress', action='store_true',
                       help='Show progress updates')
    parser.add_argument('--config', action='store_true',
                       help='Show current configuration')
    parser.add_argument('--project-root', type=str,
                       help='Project root directory')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    return parser

def show_config():
    """Display current configuration."""
    config_manager = get_config_manager()
    config = apply_env_overrides(config_manager.get_config())
    
    print("Formal Verifier Configuration")
    print("=" * 40)
    print(f"Config file: {config_manager.config_path}")
    print()
    print("API URLs:")
    print(f"  Annotator: {config.api.annotator_url}")
    print(f"  Verifier:  {config.api.verifier_url}")
    print(f"  Timeout:   {config.api.timeout}s")
    print()
    print("Verification:")
    print(f"  Inline deps:     {config.verification.inline_dependencies}")
    print(f"  Preserve temps:  {config.verification.preserve_temp_files}")
    print(f"  Max file size:   {config.verification.max_file_size}")
    print()
    
    errors = config_manager.validate_config()
    if errors:
        print("Configuration errors:")
        for key, error in errors.items():
            print(f"  {key}: {error}")
    else:
        print("✅ Configuration valid")

def progress_callback(stage: Stage, message: str = ""):
    """Handle progress updates."""
    print(f"Stage: {stage.value}")
    if message:
        print(f"Info: {message}")
    sys.stdout.flush()

def format_json_result(result, elapsed_time):
    """Format result as JSON for VS Code."""
    if result.success and result.verification_result:
        return {
            "success": True,
            "verification": result.verification_result,
            "elapsed_time": elapsed_time,
            "temp_files": result.temp_files
        }
    else:
        return {
            "success": False,
            "errors": result.errors,
            "elapsed_time": elapsed_time
        }

def main():
    """Main entry point."""
    parser = setup_args()
    args = parser.parse_args()
    
    # Handle special commands
    if args.config:
        show_config()
        return 0
    
    if not args.file:
        print("Error: No input file specified", file=sys.stderr)
        parser.print_help()
        return 1
    
    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' not found", file=sys.stderr)
        return 1
    
    try:
        # Read source file
        source_code = read_file(args.file)
        
        # Setup project root
        project_root = args.project_root or os.path.dirname(os.path.abspath(args.file))
        
        # Setup progress callback
        progress_cb = progress_callback if args.progress and not args.json else None
        
        # Apply environment overrides
        config_manager = get_config_manager()
        config = apply_env_overrides(config_manager.get_config())
        
        if args.project_root:
            config.project_root = args.project_root
        
        # Run verification
        start_time = time.time()
        
        if not args.json:
            print(f"Verifying: {args.file}")
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
            print("VERIFICATION_RESULTS_START")
            print(json.dumps(format_json_result(result, elapsed_time), indent=2))
            print("VERIFICATION_RESULTS_END")
        else:
            print("-" * 40)
            if result.success and result.verification_result:
                print(format_results(result.verification_result))
            else:
                print("❌ Verification failed:")
                for error in result.errors:
                    print(f"  - {error}")
            
            print(f"\nTime: {elapsed_time:.2f}s")
            
            if result.temp_files:
                print("\nTemp files:")
                for f in result.temp_files:
                    print(f"  {f}")
        
        # Return appropriate exit code
        if result.success:
            if result.verification_result and result.verification_result.get("verified", False):
                return 0  # Success
            else:
                return 2  # Verification failed
        else:
            return 1  # Pipeline failed
    
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        return 130
    except Exception as e:
        if args.json:
            error_result = {"success": False, "errors": [str(e)], "elapsed_time": 0}
            print("VERIFICATION_RESULTS_START")
            print(json.dumps(error_result, indent=2))
            print("VERIFICATION_RESULTS_END")
        else:
            print(f"Error: {e}", file=sys.stderr)
            if args.verbose:
                import traceback
                traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())