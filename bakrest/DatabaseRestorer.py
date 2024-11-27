import os
import queue
import time
import threading
import subprocess
from subprocess import CompletedProcess
from typing import Dict, List

class DatabaseRestorer:

    def __init__(self, server: str, password: str):
        self.server = server
        self.password = password

    def test_connection(self) -> bool:
        try:
            result: CompletedProcess = subprocess.run([
                "sqlcmd", "-S", self.server, "-U", "sa", "-P", self.password,
                "-C", "-Q", "SET NOCOUNT ON; SELECT 1", "-W", "-h", "-1"
            ],
                                                      capture_output=True,
                                                      check=True,
                                                      text=True)
            return result.stdout.strip() == "1"
        except subprocess.CalledProcessError as e:
            print(f"Connection test failed: {e.stderr}")
        except Exception as e:
            print(f"{type(e).__name__}: {e}")
        return False

    def execute_query(self, query: str) -> bool:
        try:
            subprocess.run([
                "sqlcmd", "-S", self.server, "-U", "sa", "-P", self.password,
                "-C", "-Q", query
            ],
                           capture_output=True,
                           check=True,
                           text=True)
            print(f"Query executed successfully: {query}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Query execution failed: {e.stderr}")
        return False

    def query_restore_progress(self) -> int:
        try:
            query = """
            SET NOCOUNT ON;
            SELECT percent_complete
            FROM sys.dm_exec_requests
            WHERE command IN ('RESTORE DATABASE');
            """
            result = subprocess.run([
                "sqlcmd", "-S", self.server, "-U", "sa", "-P", self.password,
                "-C", "-W", "-h", "-1", "-Q", query
            ],
                                    capture_output=True,
                                    check=True,
                                    text=True)
            output = result.stdout.strip()
            if not output:
                print("No restore progress found.")
                return 0

            return int(float(output))
        except subprocess.CalledProcessError as e:
            print(f"Query execution failed: {e.stderr}")
        except ValueError as ve:
            print(f"Failed to parse restore progress: {ve}")
        return 0

    def restore_and_track(self, db_name: str, backup_file_path: str,
                          logical_files: List[Dict[str, str]],
                          restore_dir: str) -> bool:

        result_queue = queue.Queue()

        def restore_worker():
            try:
                self.restore_database(db_name, backup_file_path, logical_files,
                                      restore_dir)
                result_queue.put({"status": "success"})
            except Exception as e:
                result_queue.put({"status": "error", "details": str(e)})

        def progress_worker():
            while True:
                if not restore_thread.is_alive():
                    print(
                        "Restore thread is no longer running. Exiting progress monitor."
                    )
                    break

                progress = self.query_restore_progress()
                print(f"Progress: {progress}%")
                if progress >= 100:
                    break
                time.sleep(1)

        restore_thread = threading.Thread(target=restore_worker)
        progress_thread = threading.Thread(target=progress_worker)

        restore_thread.start()
        progress_thread.start()

        restore_thread.join()
        progress_thread.join()

        result = result_queue.get()
        if result["status"] == "error":
            print(f"Restore failed: {result['details']}")
            return False
        return True

    def generate_move_statements(
            self, db_name: str, restore_dir: str,
            logical_files: List[Dict[str, str]]) -> List[str]:
        type_counts = {"data": 0, "log": 0}
        type_counters = {"data": 0, "log": 0}
        moves = []

        for file in logical_files:
            ltype = file.get("type")
            if ltype in type_counts:
                type_counts[ltype] += 1

        for file in logical_files:
            lname = file.get("logical_name")
            ltype = file.get("type")
            type_counters[ltype] += 1

            if not lname or not ltype:
                print(f"Warning: Missing keys in logical file: {file}")
                continue

            ext = ".mdf" if ltype == "data" else "_Log.ldf" if ltype == "log" else ""
            if not ext:
                print(f"Warning: Unknown file type '{ltype}' for {lname}")
                continue

            if type_counters[ltype] == 1:
                new_name = os.path.join(restore_dir, f"{db_name}{ext}")
            else:
                new_name = os.path.join(
                    restore_dir, f"{db_name}_{type_counters[ltype]}{ext}")

            moves.append(f"MOVE '{lname}' TO '{new_name}'")
        return moves

    def restore_database(self, db_name: str, backup_file_path: str,
                         logical_files: List[Dict[str,
                                                  str]], restore_dir: str):
        print(f"Starting restore process for database: {db_name}")

        exists = False

        check_query = f"SELECT name FROM sys.databases WHERE name = '{db_name}';"
        if self.execute_query(check_query): exists = True

        moves = self.generate_move_statements(db_name, restore_dir,
                                              logical_files)

        if not moves:
            raise Exception("No valid logical files to restore")

        off_query = f"""
        ALTER DATABASE [{db_name}] SET OFFLINE WITH ROLLBACK IMMEDIATE;
        """

        restore_query = f"""
        RESTORE DATABASE [{db_name}]
        FROM DISK = '{backup_file_path}'
        WITH
             {',\n             '.join(moves)},
             REPLACE,
             STATS=1;
        """

        on_query = f"""
        ALTER DATABASE [{db_name}] SET ONLINE
        """
        if exists:
            print(f"Setting database {db_name} offline.")
            if not self.execute_query(off_query):
                raise Exception(f"Failed to set database {db_name} offline.")

        if not self.execute_query(restore_query):
            raise Exception(f"Failed to restore the database {db_name}.")

        if exists:
            print(f"Setting database {db_name} online.")
            if not self.execute_query(on_query):
                raise Exception(f"Failed to set database {db_name} online.")
