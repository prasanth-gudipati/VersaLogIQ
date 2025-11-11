#!/usr/bin/env python3
"""
Comprehensive test runner for VersaLogIQ test automation
"""

import os
import sys
import unittest
import subprocess
import argparse
import time
import json
from pathlib import Path

# Add project paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'unit'))
sys.path.insert(0, str(project_root / 'integration'))
sys.path.insert(0, str(project_root / 'mock'))
sys.path.insert(0, str(project_root / '..' / 'backend'))

class TestRunner:
    """Main test runner for VersaLogIQ test automation"""
    
    def __init__(self):
        self.project_root = project_root
        self.results = {
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'skipped': 0,
            'execution_time': 0,
            'coverage': None,
            'test_results': []
        }
    
    def discover_tests(self, test_type='all', pattern='test_*.py'):
        """Discover tests based on type and pattern"""
        test_suites = unittest.TestSuite()
        
        if test_type in ['all', 'unit']:
            # Discover unit tests
            unit_tests = unittest.TestLoader().discover(
                str(self.project_root / 'unit'), 
                pattern=pattern
            )
            test_suites.addTest(unit_tests)
        
        if test_type in ['all', 'integration', 'api']:
            # Discover integration tests
            integration_tests = unittest.TestLoader().discover(
                str(self.project_root / 'integration'), 
                pattern=pattern
            )
            test_suites.addTest(integration_tests)
        
        return test_suites
    
    def run_tests_with_coverage(self, test_suite, verbose=False):
        """Run tests with coverage analysis"""
        try:
            import coverage
            cov = coverage.Coverage(source=[str(self.project_root / '..' / 'backend')])
            cov.start()
            
            # Run tests
            runner = unittest.TextTestRunner(
                verbosity=2 if verbose else 1,
                stream=sys.stdout,
                buffer=True
            )
            
            start_time = time.time()
            result = runner.run(test_suite)
            end_time = time.time()
            
            cov.stop()
            cov.save()
            
            # Generate coverage report
            coverage_report = self.generate_coverage_report(cov)
            
            self.results.update({
                'total_tests': result.testsRun,
                'passed': result.testsRun - len(result.failures) - len(result.errors),
                'failed': len(result.failures),
                'errors': len(result.errors),
                'execution_time': end_time - start_time,
                'coverage': coverage_report
            })
            
            return result
            
        except ImportError:
            print("⚠️  Coverage module not available. Running tests without coverage.")
            return self.run_tests_without_coverage(test_suite, verbose)
    
    def run_tests_without_coverage(self, test_suite, verbose=False):
        """Run tests without coverage analysis"""
        runner = unittest.TextTestRunner(
            verbosity=2 if verbose else 1,
            stream=sys.stdout,
            buffer=True
        )
        
        start_time = time.time()
        result = runner.run(test_suite)
        end_time = time.time()
        
        self.results.update({
            'total_tests': result.testsRun,
            'passed': result.testsRun - len(result.failures) - len(result.errors),
            'failed': len(result.failures),
            'errors': len(result.errors),
            'execution_time': end_time - start_time,
            'coverage': None
        })
        
        return result
    
    def generate_coverage_report(self, cov):
        """Generate coverage report"""
        try:
            # Get coverage data
            coverage_data = {}
            
            # Create temporary report
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                cov.report(file=f, show_missing=True)
                report_file = f.name
            
            # Read and parse coverage report
            with open(report_file, 'r') as f:
                report_content = f.read()
            
            # Clean up temp file
            os.unlink(report_file)
            
            # Parse coverage percentage
            lines = report_content.split('\n')
            for line in lines:
                if 'TOTAL' in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            coverage_data['total_percentage'] = parts[-1].rstrip('%')
                        except:
                            coverage_data['total_percentage'] = 'N/A'
                    break
            
            coverage_data['report'] = report_content
            return coverage_data
            
        except Exception as e:
            print(f"⚠️  Error generating coverage report: {e}")
            return None
    
    def run_specific_test(self, test_path, verbose=False):
        """Run a specific test file or test case"""
        try:
            # Load specific test
            loader = unittest.TestLoader()
            
            if '::' in test_path:
                # Specific test method
                module_path, test_method = test_path.split('::')
                module = __import__(module_path.replace('/', '.').replace('.py', ''))
                suite = loader.loadTestsFromName(test_method, module)
            else:
                # Entire test file
                if test_path.endswith('.py'):
                    test_path = test_path[:-3]
                
                suite = loader.loadTestsFromName(test_path.replace('/', '.'))
            
            return self.run_tests_without_coverage(suite, verbose)
            
        except Exception as e:
            print(f"❌ Error running specific test {test_path}: {e}")
            return None
    
    def validate_test_environment(self):
        """Validate test environment and dependencies"""
        print("🔍 Validating test environment...")
        
        validation_errors = []
        
        # Check Python version
        if sys.version_info < (3, 6):
            validation_errors.append("Python 3.6+ required")
        
        # Check required modules
        required_modules = ['unittest', 'paramiko', 'json', 'pathlib']
        optional_modules = ['coverage']
        
        for module in required_modules:
            try:
                __import__(module)
                print(f"✅ {module}")
            except ImportError:
                validation_errors.append(f"Required module {module} not found")
                print(f"❌ {module}")
        
        for module in optional_modules:
            try:
                __import__(module)
                print(f"✅ {module} (optional)")
            except ImportError:
                print(f"⚠️  {module} (optional, not available)")
        
        # Check test files exist
        test_files = [
            'unit/test_flavor_detection.py',
            'unit/test_ssh_connection.py',
            'integration/test_versalogiq_workflow.py',
            'mock/mock_responses.py',
            'test_config.py'
        ]
        
        for test_file in test_files:
            file_path = self.project_root / test_file
            if file_path.exists():
                print(f"✅ {test_file}")
            else:
                validation_errors.append(f"Test file {test_file} not found")
                print(f"❌ {test_file}")
        
        # Check backend files
        backend_files = [
            '../backend/versalogiq_app.py',
            '../config/server_flavors.json'
        ]
        
        for backend_file in backend_files:
            file_path = self.project_root / backend_file
            if file_path.exists():
                print(f"✅ {backend_file}")
            else:
                validation_errors.append(f"Backend file {backend_file} not found")
                print(f"❌ {backend_file}")
        
        if validation_errors:
            print(f"\n❌ Validation failed with {len(validation_errors)} errors:")
            for error in validation_errors:
                print(f"   • {error}")
            return False
        else:
            print("\n✅ Test environment validation passed!")
            return True
    
    def generate_test_report(self, output_file=None):
        """Generate comprehensive test report"""
        report = {
            'test_run_summary': {
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_tests': self.results['total_tests'],
                'passed': self.results['passed'],
                'failed': self.results['failed'],
                'errors': self.results['errors'],
                'success_rate': round(self.results['passed'] / max(self.results['total_tests'], 1) * 100, 2),
                'execution_time_seconds': round(self.results['execution_time'], 2)
            },
            'coverage': self.results['coverage'],
            'environment': {
                'python_version': sys.version,
                'platform': sys.platform,
                'working_directory': str(self.project_root)
            }
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"📝 Test report saved to {output_file}")
        
        return report
    
    def print_summary(self):
        """Print test execution summary"""
        print("\n" + "="*60)
        print("🧪 VERSALOGIQ TEST AUTOMATION SUMMARY")
        print("="*60)
        
        # Test results
        total = self.results['total_tests']
        passed = self.results['passed']
        failed = self.results['failed']
        errors = self.results['errors']
        
        print(f"📊 Tests Run: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"💥 Errors: {errors}")
        
        if total > 0:
            success_rate = (passed / total) * 100
            print(f"📈 Success Rate: {success_rate:.1f}%")
        
        print(f"⏱️  Execution Time: {self.results['execution_time']:.2f} seconds")
        
        # Coverage information
        if self.results['coverage']:
            coverage_pct = self.results['coverage'].get('total_percentage', 'N/A')
            print(f"📋 Code Coverage: {coverage_pct}%")
        
        # Final status
        print("\n" + "-"*60)
        if failed == 0 and errors == 0:
            print("🎉 ALL TESTS PASSED!")
        else:
            print("⚠️  SOME TESTS FAILED - Check details above")
        print("-"*60)

def main():
    """Main entry point for test runner"""
    parser = argparse.ArgumentParser(description='VersaLogIQ Test Automation Runner')
    
    parser.add_argument('--type', choices=['all', 'unit', 'integration', 'api'], 
                       default='all', help='Type of tests to run')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Verbose test output')
    parser.add_argument('--coverage', action='store_true', 
                       help='Run with code coverage analysis')
    parser.add_argument('--validate', action='store_true', 
                       help='Validate test environment only')
    parser.add_argument('--test', help='Run specific test file or method')
    parser.add_argument('--pattern', default='test_*.py', 
                       help='Test file pattern to discover')
    parser.add_argument('--report', help='Generate JSON report file')
    parser.add_argument('--quick', action='store_true', 
                       help='Run quick tests only (skip performance tests)')
    
    args = parser.parse_args()
    
    # Initialize test runner
    runner = TestRunner()
    
    print("🚀 VersaLogIQ Test Automation Runner")
    print("="*50)
    
    # Validate environment if requested
    if args.validate:
        success = runner.validate_test_environment()
        sys.exit(0 if success else 1)
    
    # Always validate before running tests
    if not runner.validate_test_environment():
        print("❌ Environment validation failed. Fix issues before running tests.")
        sys.exit(1)
    
    # Run specific test if specified
    if args.test:
        print(f"\n🎯 Running specific test: {args.test}")
        result = runner.run_specific_test(args.test, args.verbose)
        if result:
            runner.print_summary()
        sys.exit(0 if result and result.wasSuccessful() else 1)
    
    # Discover and run tests
    print(f"\n🔍 Discovering {args.type} tests...")
    test_suite = runner.discover_tests(args.type, args.pattern)
    
    if test_suite.countTestCases() == 0:
        print("❌ No tests discovered!")
        sys.exit(1)
    
    print(f"📋 Found {test_suite.countTestCases()} tests")
    
    # Set environment variables for quick mode
    if args.quick:
        os.environ['QUICK_TESTS'] = '1'
    
    # Run tests
    print(f"\n🏃 Running tests...")
    if args.coverage:
        result = runner.run_tests_with_coverage(test_suite, args.verbose)
    else:
        result = runner.run_tests_without_coverage(test_suite, args.verbose)
    
    # Generate report
    if args.report:
        runner.generate_test_report(args.report)
    
    # Print summary
    runner.print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)

if __name__ == '__main__':
    main()