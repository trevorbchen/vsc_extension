VS Code Formal Verifier Extension (Enhanced)
A VS Code extension that integrates with external APIs to perform formal verification of C programs using ACSL annotations and tools like Frama-C.

🆕 What's New in v0.2.0
This enhanced version addresses the key limitations identified in the original prototype:

✅ Major Improvements
🔧 Robust Configuration Management: JSON-based configuration with environment variable overrides
🔗 Enhanced Dependency Resolution: Proper AST-level parsing and safe code merging
📊 Progress Tracking: Real-time progress updates with stage-by-stage feedback
🛠️ Better Error Handling: Comprehensive error reporting and graceful failure handling
🧪 Test Suite: Comprehensive unit and integration tests
🎯 VS Code Integration: Diagnostics, progress notifications, and better UI
⚙️ Flexible Configuration: Configurable through VS Code settings and config files
🚀 Quick Start
Prerequisites
VS Code 1.60.0 or higher
Python 3.7+ with required dependencies
C compiler (optional, for testing)
Installation
Clone the repository:
bash
git clone https://github.com/your-username/vscode-formal-verifier.git
cd vscode-formal-verifier
Install Python dependencies:
bash
pip install -r Requirements.txt
Load in VS Code:
Open VS Code
Go to Extensions → Install from VSIX (or load in development mode)
Open any .c file
Use Ctrl+Shift+V or Command Palette → "Run Formal Verification"
🎯 Usage
Basic Verification
Open a C source file in VS Code
Press Ctrl+Shift+V (or Cmd+Shift+V on Mac)
Watch the progress notification
View results in the output panel or as diagnostics
Command Line Usage
The backend can also be used directly from the command line:

bash
# Basic verification
python3 python/main.py main.c

# JSON output for tooling integration
python3 python/main.py main.c --json

# Show progress updates
python3 python/main.py main.c --progress

# Run with custom project root
python3 python/main.py main.c --project-root /path/to/project

# Show current configuration
python3 python/main.py --config

# Run self-tests
python3 python/main.py --test
Configuration
VS Code Settings
Configure through VS Code settings (Ctrl+, → Search "formalVerifier"):

json
{
  "formalVerifier.pythonPath": "python3",
  "formalVerifier.autoSaveBeforeVerify": true,
  "formalVerifier.inlineDependencies": true,
  "formalVerifier.resultDisplayMode": "both",
  "formalVerifier.api.annotatorUrl": "http://localhost:8000/annotate",
  "formalVerifier.api.verifierUrl": "http://localhost:8001/verify",
  "formalVerifier.api.timeout": 30
}
Project Configuration
Create .formalverifier.json in your project root:

json
{
  "api": {
    "annotator_url": "http://localhost:8000/annotate",
    "verifier_url": "http://localhost:8001/verify",
    "timeout": 30,
    "auth_token": "your-token-here"
  },
  "verification": {
    "inline_dependencies": true,
    "preserve_temp_files": false,
    "max_file_size": 1048576,
    "supported_extensions": [".c", ".h"]
  },
  "ui": {
    "show_progress": true,
    "auto_save_before_verify": true,
    "result_display_mode": "both"
  }
}
Environment Variables
Override configuration with environment variables:

bash
export FORMALVERIFIER_ANNOTATOR_URL="http://remote-api:8000/annotate"
export FORMALVERIFIER_VERIFIER_URL="http://remote-api:8001/verify"
export FORMALVERIFIER_AUTH_TOKEN="your-secret-token"
export FORMALVERIFIER_TIMEOUT="60"
🏗️ Architecture
Components Overview
├── extension.js                 # VS Code extension frontend
├── package.json                # Extension manifest with configuration schema
├── python/
│   ├── main.py                 # Enhanced CLI entry point
│   ├── enhanced_pipeline.py    # Core verification pipeline
│   ├── config_manager.py       # Configuration management
│   ├── utils/
│   │   ├── enhanced_dependency.py  # Advanced dependency resolution
│   │   └── file_handler.py     # File operations
│   ├── api/
│   │   ├── annotator.py        # Annotation API client
│   │   └── verifier.py         # Verification API client
│   └── ui/
│       └── results.py          # Result formatting
└── test_suite.py              # Comprehensive tests
Pipeline Stages
The verification pipeline consists of 6 stages:

Initialization: Input validation and setup
Dependency Resolution: Parse and classify #include statements
Code Merging: Safely combine source files with dependency resolution
Annotation: Add ACSL annotations via API #1
Verification: Run formal verification via API #2
Result Formatting: Process and format results for display
Enhanced Dependency Resolution
The new dependency system:

Parses include statements with proper C preprocessor semantics
Builds dependency graphs to handle complex project structures
Safely merges code with include guards and duplicate prevention
Handles circular dependencies gracefully
Supports nested includes and relative paths
🛠️ Development
Running Tests
bash
# Run all tests
python3 python/test_suite.py

# Run specific test class
python3 -m unittest test_suite.TestDependencyResolution

# Run with verbose output
python3 python/test_suite.py --verbose
API Implementation
The system is designed to work with two APIs:

Annotation API (API #1)
python
# Expected interface
def annotate_code(source_code: str) -> str:
    """Add ACSL annotations to C source code."""
    # Return annotated code
Verification API (API #2)
python
# Expected interface
def verify_code(annotated_code: str) -> dict:
    """Verify annotated C code."""
    # Return: {"verified": bool, "errors": [str]}
Implementing Real APIs
Replace the stubs in python/api/ with actual implementations:

REST API Client:
python
import requests
from config_manager import get_config

def annotate_code(source_code: str) -> str:
    config = get_config()
    response = requests.post(
        config.api.annotator_url,
        json={"code": source_code},
        timeout=config.api.timeout,
        headers={"Authorization": f"Bearer {config.api.auth_
