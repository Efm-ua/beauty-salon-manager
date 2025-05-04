#!/usr/bin/env python3
"""
Test Runner Script for Beauty Salon Manager

This script provides a command-line interface for running different types of tests
and generating code coverage reports. It supports various options for controlling
which tests to run and how to format the results.

Usage:
    python run_tests.py [options]

Options:
    Test Categories:
    --unit         Run only unit tests
    --integration  Run only integration tests
    --functional   Run only functional tests
    (no options)   Run all tests

    Coverage Options:
    --cov          Enable code coverage measurement
    --html         Generate HTML coverage report
    --xml          Generate XML coverage report

    Output Options:
    -v, --verbose  Show detailed test output
    --quiet        Show minimal test output

    Maintenance:
    --clean        Remove temporary test files
"""

import argparse
import subprocess
import sys
import os
import shutil


def parse_arguments():
    """Parse command line arguments for the test runner."""
    parser = argparse.ArgumentParser(description="Run tests for Beauty Salon Manager")

    # Test category options
    test_category = parser.add_argument_group("Test Categories")
    test_category.add_argument(
        "--unit", action="store_true", help="Run only unit tests"
    )
    test_category.add_argument(
        "--integration", action="store_true", help="Run only integration tests"
    )
    test_category.add_argument(
        "--functional", action="store_true", help="Run only functional tests"
    )

    # Coverage options
    coverage = parser.add_argument_group("Coverage Options")
    coverage.add_argument(
        "--cov", action="store_true", help="Enable code coverage measurement"
    )
    coverage.add_argument(
        "--html", action="store_true", help="Generate HTML coverage report"
    )
    coverage.add_argument(
        "--xml", action="store_true", help="Generate XML coverage report"
    )

    # Output options
    output = parser.add_argument_group("Output Options")
    output.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed test output"
    )
    output.add_argument("--quiet", action="store_true", help="Show minimal test output")

    # Maintenance options
    maintenance = parser.add_argument_group("Maintenance")
    maintenance.add_argument(
        "--clean", action="store_true", help="Remove temporary test files"
    )

    return parser.parse_args()


def clean_temp_files():
    """Remove temporary files created during testing."""
    temp_directories = [
        ".pytest_cache",
        ".coverage",
        "htmlcov",
        "__pycache__",
    ]

    for directory in temp_directories:
        if os.path.isdir(directory):
            print(f"Removing directory: {directory}")
            shutil.rmtree(directory)
        elif os.path.isfile(directory):
            print(f"Removing file: {directory}")
            os.remove(directory)

    # Clean __pycache__ directories recursively
    for root, dirs, _ in os.walk("."):
        for directory in dirs:
            if directory == "__pycache__":
                pycache_path = os.path.join(root, directory)
                print(f"Removing directory: {pycache_path}")
                shutil.rmtree(pycache_path)

    # Remove .coverage.* files
    for file in os.listdir("."):
        if file.startswith(".coverage."):
            print(f"Removing file: {file}")
            os.remove(file)


def build_pytest_command(args):
    """Build the pytest command based on provided arguments."""
    cmd = ["pytest"]

    # Determine which tests to run
    if args.unit:
        cmd.append("tests/unit")
    elif args.integration:
        cmd.append("tests/integration")
    elif args.functional:
        cmd.append("tests/functional")
    else:
        cmd.append("tests")

    # Add verbosity options
    if args.verbose:
        cmd.append("-v")
    if args.quiet:
        cmd.append("-q")

    # Add coverage options
    if args.cov:
        cmd.append("--cov=app")

        if args.html:
            cmd.append("--cov-report=html")
        if args.xml:
            cmd.append("--cov-report=xml")

        # Always include terminal coverage report
        cmd.append("--cov-report=term")

    return cmd


def run_tests(args):
    """Run the tests with the specified options."""
    try:
        cmd = build_pytest_command(args)
        print(f"Running command: {' '.join(cmd)}")

        result = subprocess.run(cmd, check=False)
        return result.returncode

    except subprocess.SubprocessError as e:
        print(f"Error running tests: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1


def main():
    """Main function to run the test script."""
    args = parse_arguments()

    # Handle clean option separately
    if args.clean:
        clean_temp_files()
        return 0

    # Check for conflicting arguments
    if args.verbose and args.quiet:
        print("Error: Cannot use both --verbose and --quiet options.")
        return 1

    # Check if coverage reports are requested without --cov
    if (args.html or args.xml) and not args.cov:
        print(
            "Warning: HTML or XML reports requested but --cov not enabled. Adding --cov option."
        )
        args.cov = True

    # Run the tests
    return_code = run_tests(args)

    # Print a message about the coverage report if generated
    if args.cov:
        if args.html:
            print("\nHTML coverage report generated in 'htmlcov' directory.")
            print("Open 'htmlcov/index.html' in a browser to view it.")
        if args.xml:
            print("\nXML coverage report generated: 'coverage.xml'")

    return return_code


if __name__ == "__main__":
    sys.exit(main())
