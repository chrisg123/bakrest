import time
import threading
import queue
from typing import Dict
import requests

class FileUploader:
    def __init__(self, base_url: str):
        self.base_url = base_url


    def test_connection(self) -> bool:
        try:
            r = requests.get(self.base_url, timeout=30)
            r.raise_for_status()
            m = r.json().get("message")
            if "server is listening" not in str(m).lower():
                raise ValueError(f"Unexpected server response: {m}")

            return True
        except Exception as e:
            print(f"{type(e).__name__}: {e}")
            return False

    def request_upload_id(self):
        """Request an upload ID from the server."""
        response = requests.get(f"{self.base_url}/upload-request", timeout=30)
        response.raise_for_status()
        upload_id = response.json().get("upload_id")
        if not upload_id:
            raise ValueError("Failed to retrieve upload ID")
        return upload_id

    def upload_file(self, upload_id, file_path) -> Dict:
        """Upload the file to the server."""
        upload_url = f"{self.base_url}/upload/{upload_id}"
        print(f"Uploading file to {upload_url}")
        with open(file_path, "rb") as f:
            response = requests.post(upload_url, files={"file": f}, timeout=30)
            response.raise_for_status()

        return response.json()

    def poll_progress(self, upload_id):
        """Poll the server for upload progress."""
        progress_url = f"{self.base_url}/progress/{upload_id}"
        while True:
            response = requests.get(progress_url, timeout=30)
            response.raise_for_status()
            progress_data = response.json()

            if "progress" not in progress_data:
                print("Unexpected progress data:", progress_data)
                break

            progress = progress_data["progress"]
            print(f"Progress: {progress}")

            if progress == "100%":
                print("Upload complete!")
                break

            time.sleep(1)

    def upload_and_track(self, file_path: str) -> Dict:
        try:
            upload_id = self.request_upload_id()
            print(f"Obtained upload ID: {upload_id}")

            result_queue = queue.Queue()

            def upload_worker():
                try:
                    result = self.upload_file(upload_id, file_path)
                    result_queue.put(result)
                except Exception as e:
                    result_queue.put({"error": str(e)})

            poll_thread = threading.Thread(
                target=self.poll_progress, args=(upload_id,)
            )

            upload_thread = threading.Thread(target=upload_worker)
            upload_thread.start()
            poll_thread.start()

            upload_thread.join()
            poll_thread.join()

            return result_queue.get()

        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
