import os
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

    def upload_file(self, upload_id, file_path):
        file_size = os.path.getsize(file_path)
        uploaded_size = 0
        last_print_time = time.time()

        def data_generator():
            nonlocal uploaded_size
            nonlocal last_print_time

            for chunk in self.chunk_reader(file_path):
                uploaded_size += len(chunk)
                now = time.time()
                if now - last_print_time >= 1:
                    percent = (uploaded_size / file_size) * 100
                    print(f"Upload progress: {percent:.1f}%")
                    last_print_time = now
                yield chunk

        upload_url = f"{self.base_url}/upload/{upload_id}"
        response = requests.post(
            upload_url,
            data=data_generator(),
            headers={'X-Filename': os.path.basename(file_path)},
            stream=True,
            timeout=120
        )
        response.raise_for_status()
        return response.json()

    def upload_and_track(self, file_path: str) -> Dict:
        upload_id = self.request_upload_id()
        print(f"Obtained upload ID: {upload_id}")
        result_queue = queue.Queue()

        def upload_worker():
            try:
                result = self.upload_file(upload_id, file_path)
                result_queue.put({"upload_result": result})
            except Exception as e:
                msg = f"Upload Error: {str(e)}"
                print(msg)
                result_queue.put({"error": msg})

        upload_thread = threading.Thread(target=upload_worker)
        upload_thread.start()

        progress_url = f"{self.base_url}/progress/{upload_id}"
        polling_complete = False

        while upload_thread.is_alive() and not polling_complete:

            try:
                response = requests.get(progress_url, timeout=30)
                response.raise_for_status()
                progress_data = response.json()

                if "progress" not in progress_data:
                    print("Unexpected progress data:", progress_data)
                    result_queue.put({"error": "Unexpected progress data"})
                    polling_complete = True
                    break

                progress = progress_data["progress"]

                if int(progress.rstrip('%')) > 0:
                    print(f"Server Progress: {progress}")

                if progress == "100%":
                    print("Upload complete!")
                    polling_complete = True

            except Exception as e:
                print(f"Polling error: {e}")
                result_queue.put({"error": f"Polling Error: {str(e)}"})
                polling_complete = True
                break

            time.sleep(1)

        upload_thread.join()

        upload_result = None
        errors = []

        while not result_queue.empty():
            result = result_queue.get()
            if "upload_result" in result:
                upload_result = result["upload_result"]
            elif "error" in result:
                errors.append(result["error"])

        if upload_result:
            if errors:
                upload_result["warnings"] = " | ".join(errors)
            return upload_result
        elif errors:
            return {"error": " | ".join(errors)}

        return {"error": "No upload result."}

    def chunk_reader(self, file_path, chunk_size=4096):
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(chunk_size)
                if not data: break
                yield data

