#!/usr/bin/env python3
"""
Claude Code Runner - PTY-based Claude Code execution wrapper

Run Claude Code in non-interactive environments using pseudo-terminal (PTY),
automatically handle confirmation prompts, and sync file changes.
"""

import os
import pty
import select
import subprocess
import sys
import tempfile
import shutil
import time


def run_claude_code(workdir, prompt, user='lighthouse', timeout=300):
    """
    Run Claude Code task using PTY
    
    Args:
        workdir: Working directory path
        prompt: Natural language task description
        user: User to run as (default: lighthouse)
        timeout: Timeout in seconds (default: 300)
        
    Returns:
        Command output (stdout + stderr)
    """
    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix='claude-task-')
    project_name = os.path.basename(os.path.abspath(workdir))
    temp_workdir = os.path.join(temp_dir, project_name)
    
    try:
        # Copy project to temporary directory
        print(f"[INFO] Copying project to temp directory: {temp_workdir}", file=sys.stderr)
        shutil.copytree(workdir, temp_workdir, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
        
        # Change permissions
        shutil.chown(temp_dir, user=user, group=user)
        for root, dirs, files in os.walk(temp_workdir):
            for d in dirs:
                shutil.chown(os.path.join(root, d), user=user, group=user)
            for f in files:
                shutil.chown(os.path.join(root, f), user=user, group=user)
        
        # Create PTY
        master_fd, slave_fd = pty.openpty()
        
        # Set environment variables
        env = os.environ.copy()
        env['TERM'] = 'xterm-256color'
        env['HOME'] = f'/home/{user}'
        
        # Build command
        cmd = [
            'su', '-', user, '-c',
            f'cd {temp_workdir} && claude --print "{prompt}" 2>&1'
        ]
        
        print(f"[INFO] Starting Claude Code task...", file=sys.stderr)
        
        # Start process
        process = subprocess.Popen(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=env,
            preexec_fn=os.setsid
        )
        
        os.close(slave_fd)
        output = b''
        
        try:
            while True:
                readable, _, _ = select.select([master_fd], [], [], timeout)
                if master_fd in readable:
                    try:
                        data = os.read(master_fd, 4096)
                        if not data:
                            break
                        output += data
                        # Real-time output to stderr
                        print(data.decode('utf-8', errors='replace'), end='', flush=True, file=sys.stderr)
                        
                        # Auto-respond to confirmation prompts
                        if b'Do you want to' in output or b'proceed' in output.lower() or b'continue' in output.lower():
                            print("[INFO] Detected confirmation prompt, auto-responding 'y'", file=sys.stderr)
                            time.sleep(0.5)
                            os.write(master_fd, b'y\n')
                            output = b''
                            
                    except OSError:
                        break
                
                if process.poll() is not None:
                    break
                    
        finally:
            os.close(master_fd)
            if process.poll() is None:
                process.terminate()
                process.wait()
        
        exit_code = process.returncode
        
        # Sync changes back to original directory
        if exit_code == 0:
            print(f"[INFO] Syncing changes back to original directory...", file=sys.stderr)
            _sync_changes(temp_workdir, workdir)
        
        return output.decode('utf-8', errors='replace')
        
    finally:
        # Cleanup temporary directory
        print(f"[INFO] Cleaning up temporary directory...", file=sys.stderr)
        shutil.rmtree(temp_dir, ignore_errors=True)


def _sync_changes(source_dir, target_dir):
    """
    Sync changes from temporary directory back to original directory
    
    Args:
        source_dir: Source directory (temp directory)
        target_dir: Target directory (original project directory)
    """
    for root, dirs, files in os.walk(source_dir):
        # Calculate relative path
        rel_path = os.path.relpath(root, source_dir)
        target_root = os.path.join(target_dir, rel_path) if rel_path != '.' else target_dir
        
        # Ensure target directory exists
        if not os.path.exists(target_root):
            os.makedirs(target_root)
        
        for file in files:
            source_file = os.path.join(root, file)
            target_file = os.path.join(target_root, file)
            
            # Copy if file doesn't exist or has been modified
            if not os.path.exists(target_file):
                print(f"[SYNC] Added: {os.path.join(rel_path, file) if rel_path != '.' else file}", file=sys.stderr)
                shutil.copy2(source_file, target_file)
            elif os.path.getmtime(source_file) > os.path.getmtime(target_file):
                print(f"[SYNC] Updated: {os.path.join(rel_path, file) if rel_path != '.' else file}", file=sys.stderr)
                shutil.copy2(source_file, target_file)


def main():
    """Command line entry point"""
    if len(sys.argv) < 3:
        print("Usage: python3 run_claude.py <workdir> <prompt> [user] [timeout]", file=sys.stderr)
        print("Example: python3 run_claude.py /root/repo/my-project 'Add user authentication' lighthouse 300", file=sys.stderr)
        sys.exit(1)
    
    workdir = sys.argv[1]
    prompt = sys.argv[2]
    user = sys.argv[3] if len(sys.argv) > 3 else 'lighthouse'
    timeout = int(sys.argv[4]) if len(sys.argv) > 4 else 300
    
    if not os.path.exists(workdir):
        print(f"Error: Directory not found: {workdir}", file=sys.stderr)
        sys.exit(1)
    
    result = run_claude_code(workdir, prompt, user, timeout)
    print(result)


if __name__ == "__main__":
    main()
