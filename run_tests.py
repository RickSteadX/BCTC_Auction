"""
Test runner script for BCTC Auction Bot
Runs all unit tests and provides coverage report
"""
import subprocess
import sys
import os

def run_tests():
    """Run all unit tests"""
    print("🧪 BCTC Auction Bot - Unit Tests")
    print("=" * 40)
    
    # Change to project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    
    try:
        # Run pytest with verbose output
        result = subprocess.run([
            sys.executable, "-m", "pytest",
            "tests/",
            "-v",
            "--tb=short",
            "--durations=10"
        ], capture_output=False, text=True)
        
        print("\n" + "=" * 40)
        if result.returncode == 0:
            print("✅ All tests passed!")
        else:
            print("❌ Some tests failed.")
            
        return result.returncode == 0
        
    except FileNotFoundError:
        print("❌ pytest not found. Install with: pip install pytest pytest-asyncio")
        return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def run_specific_test(test_file):
    """Run a specific test file"""
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest",
            f"tests/{test_file}",
            "-v"
        ], capture_output=False, text=True)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Error running {test_file}: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific test file
        test_file = sys.argv[1]
        if not test_file.startswith("test_"):
            test_file = f"test_{test_file}"
        if not test_file.endswith(".py"):
            test_file = f"{test_file}.py"
            
        print(f"🧪 Running specific test: {test_file}")
        success = run_specific_test(test_file)
    else:
        # Run all tests
        success = run_tests()
    
    sys.exit(0 if success else 1)