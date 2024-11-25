import os
import sys
import argparse
from signal import signal, SIGINT
from .FileUploader import FileUploader
from .DatabaseRestorer import DatabaseRestorer

def sigint(
    _signum,
    _stackframe,
):
    sys.stdout.write("\nexit\n")
    sys.exit(0)

def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Upload and restore a SQL Server .bak to a remote server")

    parser.add_argument(
        "base_url",
        help="Base URL of the server (e.g., http://127.0.0.1:5000)")
    parser.add_argument("file_path", help="Path to the file to be uploaded")
    parser.add_argument("sql_server_name",
                        help="Path to the file to be uploaded")
    parser.add_argument("database_name",
                        help="Path to the file to be uploaded")
    parser.add_argument(
        "--password",
        help="SQL Server SA password (can also use SA_PASSWORD env variable)")

    return parser.parse_args(argv)

def main(argv):
    signal(SIGINT, sigint)
    args = parse_args(argv[1:])
    password = args.password or os.environ.get("SA_PASSWORD")

    if not password:
        print(
            "SA password not provided. Use --password or set SA_PASSWORD environment variable.",
            file=sys.stderr)
        sys.exit(1)

    uploader = FileUploader(args.base_url)
    restorer = DatabaseRestorer(args.sql_server_name, password)

    if not uploader.test_connection():
        print("File uploader connection test failed", file=sys.stderr)
        sys.exit(1)

    if not restorer.test_connection():
        print("Database restorer connection test failed", file=sys.stderr)
        sys.exit(1)

    try:
        result = uploader.upload_and_track(args.file_path)
    except Exception as e:
        print(f"Error during file upload: {e}", file=sys.stderr)
        sys.exit(1)

    req_keys = ["file_path", "suggested_restore_dir", "logical_files"]
    if not result or not all(key in result for key in req_keys):
        print(
            f"Unexpected upload result. Missing required keys: {', '.join(req_keys)}.",
            file=sys.stderr)
        sys.exit(1)

    remote_backup_file = result['file_path']
    restore_dir = result['suggested_restore_dir']
    logical_files = result['logical_files']

    print(f"Backup file uploaded successfully to: {remote_backup_file}")
    print(f"Suggested restore directory: {restore_dir}")

    restore_success = restorer.restore_and_track(args.database_name,
                                                 remote_backup_file,
                                                 logical_files, restore_dir)

    if restore_success:
        print(f"Database {args.database_name} restored successfully.")
    else:
        print(f"Failed to restore the database {args.database_name}.",
              file=sys.stderr)
        sys.exit(1)
