#!/usr/bin/env python3
"""Restore media files from backup bucket."""
import argparse
import os
import subprocess
import sys


def confirm(prompt: str) -> bool:
    response = input(f"{prompt} [y/N] ").strip().lower()
    return response in ("y", "yes")


def main():
    parser = argparse.ArgumentParser(description="Restore media files from backup")
    parser.add_argument("backup_path", help="S3 or local path to the backup")
    parser.add_argument("--dest", default="/var/www/chain_app/media",
                        help="Destination media directory (default: /var/www/chain_app/media)")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    if not args.force:
        print(f"This will RESTORE media files from:\n  Source: {args.backup_path}\n  Dest:   {args.dest}")
        if not confirm("Continue?"):
            print("Aborted.")
            sys.exit(1)

    if args.backup_path.startswith("s3://"):
        cmd = ["aws", "s3", "sync", args.backup_path, args.dest, "--no-progress"]
    else:
        cmd = ["rsync", "-avh", args.backup_path.rstrip("/") + "/", args.dest.rstrip("/") + "/"]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("OK: media restore complete")
    else:
        print(f"ERROR: restore failed with exit code {result.returncode}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
