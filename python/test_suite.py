"""
Basic test suite for the formal verifier extension.
Tests core functionality and edge cases.
"""

import unittest
import tempfile
import os
from unittest.mock import patch, MagicMock
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))

from utils.enhanced_dependency import DependencyGraph, extract_includes, classify_dependencies
from enhanced_pipeline import VerificationPipeline, PipelineStage, PipelineError
from config_manager import ConfigManager, Config, APIConfig, VerificationConfig
from utils.file_handler import read_file, save_temp_file

class TestDependencyResolution(unittest.TestCase):
    """Test dependency resolution functionality."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test files
        self.main_c = os.path.join(self.temp_dir, 'main.c')
        self.utils_h = os.path.join(self.temp_dir, 'utils.h')
        self.math_utils_c = os.path.join(self.temp_dir, 'math_utils.c')
        
        with open(self.main_c, 'w') as f:
            f.write('''#include <stdio.h>
#include "utils.h"
#include "math_utils.h"

int main() {
    printf("Hello world\\n");
    return add(2, 3);
}''')
        
        with open(self.utils_h, 'w') as f:
            f.write('''#ifndef UTILS_H
#define UTILS_H

void print_message(const char* msg);

#endif''')
        
        with open(self.math_utils_c, 'w') as f:
            f.write('''#include "utils.h"

int add(int a, int b) {
    return a + b;
}''')
    
    def tearDown(self):
        # Clean up temp files
        for file in [self.main_c, self.utils_h, self.math_utils_c]:
            if os.path.exists(file):
                os.remove(file)
        os.rmdir(self.temp_dir)
    
    def test_extract_includes(self):
        """Test basic include extraction."""
        code = '''#include <stdio.h>
#include "local.h"
#include <stdlib.h>'''
        
        includes = extract_includes(code)
        self.assertEqual(includes, ['stdio.h', 'local.h', 'stdlib.h'])
    
    def test_classify_dependencies(self):
        """Test dependency classification."""
        includes = ['stdio.h', 'utils.h', 'stdlib.h', 'math_utils.h']
        
        classified = classify_dependencies(includes, self.temp_dir)
        
        # stdio.h and stdlib.h should be external
        self.assertIn('stdio.h', classified['external'])
        self.assertIn('stdlib.h', classified['external'])
        
        # utils.h should be internal (it exists)
        self.assertIn('utils.h', classified['internal'])
    
    def test_dependency_graph(self):
        """Test dependency graph creation."""
        graph = DependencyGraph(self.temp_dir)
        
        # Add main.c to the graph
        node = graph.add_file(self.main_c)
        self.assertIsNotNone(node)
        self.assertEqual(len(node.includes), 3)  # stdio.h, utils.h, math_utils.h
        
        # Resolve dependencies
        deps = graph.resolve_dependencies(self.main_c)
        
        # Should find utils.h as internal
        self.assertIn('utils.h', deps['internal'])
        self.assertIn('stdio.h', deps['external'])

class TestConfiguration(unittest.TestCase):
    """Test configuration management."""
    
    def setUp(self):
        self.temp_config_file = tempfile.mktemp(suffix='.json')
    
    def tearDown(self):
        if os.path.exists(self.temp_config_file):
            os.remove(self.temp_config_file)
    
    def test_default_config(self):
        """Test default configuration creation."""
        config_manager = ConfigManager(self.temp_config_file)
        config = config_manager.get_config()
        
        self.assertIsInstance(config.api, APIConfig)
        self.assertIsInstance(config.verification, VerificationConfig)
        self.assertEqual(config.api.timeout, 30)
        self.assertTrue(config.verification.inline_dependencies)
    
    def test_config_validation(self):
        """Test configuration validation."""
        config_manager = ConfigManager(self.temp_config_file)
        config = config_manager.get_config()
        
        # Invalid API URL
        config.api.annotator_url = "invalid-url"
        errors = config_manager.validate_config()
        
        self.assertIn('api.annotator_url', errors)
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        config_manager = ConfigManager(self.temp_config_file)
        
        # Modify config
        config_manager.update_config(project_root="/test/path")
        success = config_manager.save_config()
        self.assertTrue(success)
        
        # Load new config manager with same file
        config_manager2 = ConfigManager(self.temp_config_file)
        config = config_manager2.get_config()
        
        self.assertEqual(config.project_root, "/test/path")

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
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_input_validation(self):
        """Test pipeline input validation."""
        pipeline = VerificationPipeline(self.temp_dir)
        
        # Test empty code
        with self.assertRaises(PipelineError):
            pipeline.run_pipeline("")
        
        # Test unsupported file extension
        with self.assertRaises(PipelineError):
            pipeline.run_pipeline(self.test_code, "test.py")
    
    @patch('enhanced_pipeline.annotate_code')
    @patch('enhanced_pipeline.verify_code')
    def test_successful_pipeline(self, mock_verify, mock_annotate):
        """Test successful pipeline execution."""
        # Mock the API calls
        mock_annotate.return_value = f"/* ACSL annotations */\n{self.test_code}"
        mock_verify.return_value = {"verified": True, "errors": []}
        
        pipeline = VerificationPipeline(self.temp_dir)
        result = pipeline.run_pipeline(self.test_code)
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.verification_result)
        self.assertTrue(result.verification_result["verified"])
        self.assertEqual(len(result.progress.errors), 0)
    
    @patch('enhanced_pipeline.annotate_code')
    @patch('enhanced_pipeline.verify_code')
    def test_failed_verification(self, mock_verify, mock_annotate):
        """Test pipeline with failed verification."""
        # Mock the API calls
        mock_annotate.return_value = f"/* ACSL annotations */\n{self.test_code}"
        mock_verify.return_value = {
            "verified": False, 
            "errors": ["Function main may not terminate"]
        }
        
        pipeline = VerificationPipeline(self.temp_dir)
        result = pipeline.run_pipeline(self.test_code)
        
        self.assertTrue(result.success)  # Pipeline succeeded, verification failed
        self.assertIsNotNone(result.verification_result)
        self.assertFalse(result.verification_result["verified"])
        self.assertEqual(len(result.verification_result["errors"]), 1)
    
    @patch('enhanced_pipeline.annotate_code')
    def test_annotation_failure(self, mock_annotate):
        """Test pipeline failure during annotation."""
        mock_annotate.side_effect = Exception("API connection failed")
        
        pipeline = VerificationPipeline(self.temp_dir)
        result = pipeline.run_pipeline(self.test_code)
        
        self.assertFalse(result.success)
        self.assertGreater(len(result.progress.errors), 0)
        self.assertIn("annotation", result.progress.errors[0].lower())
    
    def test_progress_tracking(self):
        """Test progress tracking during pipeline execution."""
        progress_updates = []
        
        def progress_callback(progress):
            progress_updates.append(progress.current_stage)
        
        pipeline = VerificationPipeline(self.temp_dir, progress_callback)
        
        with patch('enhanced_pipeline.annotate_code') as mock_annotate, \
             patch('enhanced_pipeline.verify_code') as mock_verify:
            
            mock_annotate.return_value = f"/* ACSL annotations */\n{self.test_code}"
            mock_verify.return_value = {"verified": True, "errors": []}
            
            result = pipeline.run_pipeline(self.test_code)
        
        # Check that we got progress updates for each stage
        expected_stages = [
            PipelineStage.INIT,
            PipelineStage.DEPENDENCY_RESOLUTION,
            PipelineStage.CODE_MERGING,
            PipelineStage.ANNOTATION,
            PipelineStage.VERIFICATION,
            PipelineStage.RESULT_FORMATTING
        ]
        
        for stage in expected_stages:
            self.assertIn(stage, progress_updates)

class TestFileHandling(unittest.TestCase):
    """Test file handling utilities."""
    
    def test_read_file(self):
        """Test reading files."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            f.flush()
            
            content = read_file(f.name)
            self.assertEqual(content, "test content")
            
            os.unlink(f.name)
    
    def test_save_temp_file(self):
        """Test saving temporary files."""
        content = "temporary content"
        temp_path = save_temp_file(content)
        
        self.assertTrue(os.path.exists(temp_path))
        
        with open(temp_path, 'r') as f:
            saved_content = f.read()
        
        self.assertEqual(saved_content, content)
        
        # Clean up
        os.unlink(temp_path)

class TestIntegration(unittest.TestCase):
    """Integration tests for the complete system."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a more complex test project
        self.create_test_project()
    
    def create_test_project(self):
        """Create a test C project with multiple files."""
        # main.c
        main_content = '''#include <stdio.h>
#include "math_utils.h"
#include "string_utils.h"

int main() {
    int result = add(5, 3);
    char buffer[100];
    safe_strcpy(buffer, "Hello World", sizeof(buffer));
    printf("%s: %d\\n", buffer, result);
    return 0;
}'''
        
        # math_utils.h
        math_header = '''#ifndef MATH_UTILS_H
#define MATH_UTILS_H

/*@ requires a >= 0 && b >= 0;
  @ ensures \\result == a + b;
  @*/
int add(int a, int b);

/*@ requires a > 0 && b > 0;
  @ ensures \\result == a * b;
  @*/
int multiply(int a, int b);

#endif'''
        
        # math_utils.c
        math_impl = '''#include "math_utils.h"

int add(int a, int b) {
    return a + b;
}

int multiply(int a, int b) {
    return a * b;
}'''
        
        # string_utils.h
        string_header = '''#ifndef STRING_UTILS_H
#define STRING_UTILS_H

#include <stddef.h>

/*@ requires \\valid(dest + (0..dest_size-1));
  @ requires \\valid_read(src + (0..strlen(src)));
  @ requires dest_size > 0;
  @ ensures \\result == 0 <==> strlen(src) < dest_size;
  @*/
int safe_strcpy(char *dest, const char *src, size_t dest_size);

#endif'''
        
        # string_utils.c
        string_impl = '''#include "string_utils.h"
#include <string.h>

int safe_strcpy(char *dest, const char *src, size_t dest_size) {
    if (strlen(src) >= dest_size) {
        return -1;  // Not enough space
    }
    strcpy(dest, src);
    return 0;
}'''
        
        # Write all files
        files = {
            'main.c': main_content,
            'math_utils.h': math_header,
            'math_utils.c': math_impl,
            'string_utils.h': string_header,
            'string_utils.c': string_impl
        }
        
        for filename, content in files.items():
            with open(os.path.join(self.temp_dir, filename), 'w') as f:
                f.write(content)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('enhanced_pipeline.annotate_code')
    @patch('enhanced_pipeline.verify_code')
    def test_complex_project_verification(self, mock_verify, mock_annotate):
        """Test verification of a complex project with multiple files."""
        # Mock API responses
        def mock_annotator(code):
            return f"/* Enhanced ACSL annotations */\n{code}"
        
        def mock_verifier(code):
            # Simulate some verification results
            if "safe_strcpy" in code:
                return {
                    "verified": False,
                    "errors": ["Buffer overflow possible in safe_strcpy"]
                }
            return {"verified": True, "errors": []}
        
        mock_annotate.side_effect = mock_annotator
        mock_verify.side_effect = mock_verifier
        
        # Run verification on main.c
        main_c_path = os.path.join(self.temp_dir, 'main.c')
        
        pipeline = VerificationPipeline(self.temp_dir)
        result = pipeline.run_pipeline(
            read_file(main_c_path), 
            main_c_path
        )
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.merged_code)
        self.assertIsNotNone(result.annotated_code)
        
        # Check that dependencies were resolved
        self.assertIn("math_utils", result.merged_code)
        self.assertIn("string_utils", result.merged_code)
        
        # Check verification result
        verification_result = result.verification_result
        self.assertFalse(verification_result["verified"])  # Due to buffer overflow
        self.assertGreater(len(verification_result["errors"]), 0)

class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases."""
    
    def test_invalid_file_path(self):
        """Test handling of invalid file paths."""
        pipeline = VerificationPipeline()
        
        result = pipeline.run_pipeline("int main(){return 0;}", "/nonexistent/file.c")
        
        # Should still work, just without dependency resolution
        self.assertTrue(result.success or len(result.progress.errors) > 0)
    
    def test_circular_dependencies(self):
        """Test handling of circular dependencies."""
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Create circular dependency
            file_a = os.path.join(temp_dir, 'a.h')
            file_b = os.path.join(temp_dir, 'b.h')
            
            with open(file_a, 'w') as f:
                f.write('#include "b.h"\nint func_a();')
            
            with open(file_b, 'w') as f:
                f.write('#include "a.h"\nint func_b();')
            
            graph = DependencyGraph(temp_dir)
            deps = graph.resolve_dependencies(file_a)
            
            # Should handle circular dependencies gracefully
            self.assertIsInstance(deps, dict)
            self.assertIn('internal', deps)
            self.assertIn('external', deps)
            
        finally:
            import shutil
            shutil.rmtree(temp_dir)
    
    def test_large_file_handling(self):
        """Test handling of large files."""
        # Create a large code string
        large_code = "int main() {\n" + "int x;\n" * 10000 + "return 0;\n}"
        
        pipeline = VerificationPipeline()
        
        # This should either succeed or fail gracefully
        result = pipeline.run_pipeline(large_code)
        
        # Check that it doesn't crash
        self.assertIsInstance(result, type(pipeline.run_pipeline("").__class__))

def run_tests():
    """Run all tests and return results."""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestDependencyResolution,
        TestConfiguration,
        TestPipeline,
        TestFileHandling,
        TestIntegration,
        TestErrorHandling
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result

if __name__ == '__main__':
    print("Running Formal Verifier Test Suite")
    print("=" * 50)
    
    result = run_tests()
    
    print("\n" + "=" * 50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\nOverall result: {'PASSED' if success else 'FAILED'}")
    
    sys.exit(0 if success else 1)