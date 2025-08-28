"""
Simple test suite for core functionality.
Tests the most important features without excessive complexity.
"""

import unittest
import tempfile
import os
import sys
from unittest.mock import patch

# Add project path
sys.path.insert(0, os.path.dirname(__file__))

from utils.dependency import extract_includes, classify_includes, resolve_dependencies
from pipeline import Pipeline
from config_manager import ConfigManager
from utils.file_handler import read_file, save_temp_file

class TestDependencies(unittest.TestCase):
    """Test dependency resolution."""
    
    def test_extract_includes(self):
        """Test include extraction."""
        code = '''#include <stdio.h>
#include "local.h"
#include <stdlib.h>'''
        
        includes = extract_includes(code)
        expected = ['stdio.h', 'local.h', 'stdlib.h']
        self.assertEqual(includes, expected)
    
    def test_classify_includes(self):
        """Test include classification."""
        includes = ['stdio.h', 'myheader.h', 'stdlib.h']
        
        # Create temp directory with test file
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a local header file
            local_header = os.path.join(temp_dir, 'myheader.h')
            with open(local_header, 'w') as f:
                f.write('#ifndef MYHEADER_H\n#define MYHEADER_H\n#endif')
            
            classified = classify_includes(includes, temp_dir)
            
            self.assertIn('stdio.h', classified['external'])
            self.assertIn('stdlib.h', classified['external'])
            self.assertIn('myheader.h', classified['internal'])

class TestConfig(unittest.TestCase):
    """Test configuration management."""
    
    def test_default_config(self):
        """Test default configuration."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            config_path = f.name
        
        try:
            config_manager = ConfigManager(config_path)
            config = config_manager.get_config()
            
            # Test defaults
            self.assertEqual(config.api.timeout, 30)
            self.assertTrue(config.verification.inline_dependencies)
            self.assertGreater(config.verification.max_file_size, 0)
            
        finally:
            os.unlink(config_path)

class TestPipeline(unittest.TestCase):
    """Test the verification pipeline."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_code = '''#include <stdio.h>

int main() {
    printf("Hello world\\n");
    return 0;
}'''
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('pipeline.annotate_code')
    @patch('pipeline.verify_code')
    def test_successful_pipeline(self, mock_verify, mock_annotate):
        """Test successful pipeline execution."""
        # Mock API responses
        mock_annotate.return_value = f"/* ACSL annotations */\n{self.test_code}"
        mock_verify.return_value = {"verified": True, "errors": []}
        
        pipeline = Pipeline(self.temp_dir)
        result = pipeline.run(self.test_code)
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.verification_result)
        self.assertTrue(result.verification_result["verified"])
        self.assertEqual(len(result.errors), 0)
    
    @patch('pipeline.annotate_code')
    @patch('pipeline.verify_code')
    def test_verification_failure(self, mock_verify, mock_annotate):
        """Test verification failure."""
        mock_annotate.return_value = f"/* ACSL annotations */\n{self.test_code}"
        mock_verify.return_value = {
            "verified": False,
            "errors": ["Function main may not terminate"]
        }
        
        pipeline = Pipeline(self.temp_dir)
        result = pipeline.run(self.test_code)
        
        self.assertTrue(result.success)  # Pipeline succeeded
        self.assertFalse(result.verification_result["verified"])  # But verification failed
        self.assertEqual(len(result.verification_result["errors"]), 1)
    
    def test_empty_input(self):
        """Test empty input validation."""
        pipeline = Pipeline(self.temp_dir)
        result = pipeline.run("")
        
        self.assertFalse(result.success)
        self.assertIn("empty", result.errors[0].lower())
    
    @patch('pipeline.annotate_code')
    def test_api_failure(self, mock_annotate):
        """Test API failure handling."""
        mock_annotate.side_effect = Exception("API connection failed")
        
        pipeline = Pipeline(self.temp_dir)
        result = pipeline.run(self.test_code)
        
        self.assertFalse(result.success)
        self.assertGreater(len(result.errors), 0)

class TestFileHandling(unittest.TestCase):
    """Test file operations."""
    
    def test_read_file(self):
        """Test file reading."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            f.flush()
            
            content = read_file(f.name)
            self.assertEqual(content, "test content")
            
            os.unlink(f.name)
    
    def test_save_temp_file(self):
        """Test temporary file creation."""
        content = "temp file content"
        temp_path = save_temp_file(content)
        
        self.assertTrue(os.path.exists(temp_path))
        
        with open(temp_path, 'r') as f:
            saved_content = f.read()
        
        self.assertEqual(saved_content, content)
        os.unlink(temp_path)

class TestIntegration(unittest.TestCase):
    """Basic integration tests."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
        # Create simple test project
        self.main_c = os.path.join(self.temp_dir, 'main.c')
        self.utils_h = os.path.join(self.temp_dir, 'utils.h')
        
        with open(self.main_c, 'w') as f:
            f.write('#include "utils.h"\n\nint main() { return add(1, 2); }')
        
        with open(self.utils_h, 'w') as f:
            f.write('#ifndef UTILS_H\n#define UTILS_H\nint add(int a, int b);\n#endif')
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('pipeline.annotate_code')
    @patch('pipeline.verify_code')
    def test_project_with_dependencies(self, mock_verify, mock_annotate):
        """Test verification with local dependencies."""
        mock_annotate.return_value = "/* annotated code */"
        mock_verify.return_value = {"verified": True, "errors": []}
        
        pipeline = Pipeline(self.temp_dir)
        source_code = read_file(self.main_c)
        
        result = pipeline.run(source_code, self.main_c)
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.merged_code)
        # Should contain both main and utils content
        self.assertIn("main()", result.merged_code)
        self.assertIn("UTILS_H", result.merged_code)

def run_tests():
    """Run all tests."""
    test_classes = [
        TestDependencies,
        TestConfig, 
        TestPipeline,
        TestFileHandling,
        TestIntegration
    ]
    
    suite = unittest.TestSuite()
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)

if __name__ == '__main__':
    print("Running Formal Verifier Tests")
    print("=" * 40)
    
    result = run_tests()
    
    print(f"\nTests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, trace in result.failures:
            print(f"- {test}")
    
    if result.errors:
        print("\nErrors:")
        for test, trace in result.errors:
            print(f"- {test}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\nResult: {'PASSED' if success else 'FAILED'}")
    
    sys.exit(0 if success else 1)