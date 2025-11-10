#!/usr/bin/env python3
"""
Hourly NFL Data Update Script

Complete automated workflow to update NFL predictions:
1. Collect latest scores from ESPN API
2. Rebuild dbt models with new data
3. Generate updated webpage data

This script should be run hourly via cron or similar scheduler.

Usage:
    python scripts/hourly_update.py

Schedule with cron (every hour):
    0 * * * * cd /path/to/nfl-data-stack && .venv/bin/python scripts/hourly_update.py >> logs/hourly_update.log 2>&1
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime


def log(message):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")


def run_command(cmd, description):
    """
    Run a shell command and handle errors.

    Args:
        cmd: List of command arguments
        description: Human-readable description of the command

    Returns:
        True if successful, False otherwise
    """
    log(f"Starting: {description}")
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        log(f"✓ Completed: {description}")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        log(f"✗ Failed: {description}")
        print(f"Error: {e}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False


def main():
    """Run the complete hourly update workflow."""
    log("="*80)
    log("Starting Hourly NFL Data Update")
    log("="*80)

    # Get project root directory
    project_root = Path(__file__).parent.parent
    venv_python = project_root / ".venv" / "bin" / "python"
    dbt_bin = project_root / ".venv" / "bin" / "dbt"

    # Change to project directory
    import os
    os.chdir(project_root)

    # Step 1: Collect latest scores from ESPN
    log("")
    log("STEP 1: Collecting latest NFL scores from ESPN API")
    log("-" * 80)
    success = run_command(
        [str(venv_python), "scripts/collect_espn_scores.py"],
        "ESPN score collection"
    )

    if not success:
        log("❌ Score collection failed - aborting update")
        return 1

    # Step 2: Run dbt to rebuild models
    log("")
    log("STEP 2: Rebuilding dbt models with new data")
    log("-" * 80)
    # Run from transform directory
    original_dir = os.getcwd()
    os.chdir(project_root / "transform")
    success = run_command(
        [str(dbt_bin), "run"],
        "dbt model rebuild"
    )
    os.chdir(original_dir)

    if not success:
        log("❌ dbt rebuild failed - aborting update")
        return 1

    # Step 3: Generate webpage data
    log("")
    log("STEP 3: Generating updated webpage data")
    log("-" * 80)
    success = run_command(
        [str(venv_python), "scripts/generate_full_webpage_data.py"],
        "Webpage data generation"
    )

    if not success:
        log("❌ Webpage data generation failed")
        return 1

    # Success!
    log("")
    log("="*80)
    log("✅ Hourly update completed successfully!")
    log("="*80)

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
