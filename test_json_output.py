#!/usr/bin/env python3
"""Test script to verify JSON output for notion-dev CLI commands"""

import subprocess
import json
import sys

def test_command(command, description):
    """Test a CLI command and verify JSON output"""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Command: {command}")
    print(f"{'='*60}")
    
    try:
        # Run the command
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error: Command failed with return code {result.returncode}")
            print(f"Stderr: {result.stderr}")
            return False
        
        # Try to parse the JSON output
        try:
            data = json.loads(result.stdout)
            print("✅ Valid JSON output")
            print(f"JSON structure: {json.dumps(data, indent=2)[:500]}...")
            return True
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON output: {e}")
            print(f"Output: {result.stdout[:500]}...")
            return False
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing NotionDev CLI JSON output functionality")
    
    tests = [
        ("notion-dev info --json", "Get project info in JSON format"),
        ("notion-dev tickets --json", "List tickets in JSON format"),
    ]
    
    results = []
    for command, description in tests:
        success = test_command(command, description)
        results.append((description, success))
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {description}")
    
    # Exit with appropriate code
    if all(success for _, success in results):
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()