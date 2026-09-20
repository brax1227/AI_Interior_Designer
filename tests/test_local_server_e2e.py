"""End-to-end test of the local web flow on loopback, ephemeral port, disposable outputs.

Starts local_server.DesignHandler in a thread, submits the real multipart form, and
checks what the browser would actually download. Run:
    python3 -m unittest tests.test_local_server_e2e -v
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from socketserver import TCPServer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import local_server  # noqa: E402

RUN_DIR_RE = re.compile(r'href="(/outputs/run_[0-9a-f_]+)/space_plan_report\.md"')


def multipart(fields, files=()):
    boundary = "----test" + uuid.uuid4().hex
    body = b""
    for key, value in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
    for name, filename, payload, ctype in files:
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode() + payload + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


class QuietHandler(local_server.DesignHandler):
    def log_message(self, *_args):  # keep unittest output clean
        pass


class LocalServerFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_cwd = os.getcwd()
        os.chdir(local_server.BASE_DIR)  # static files are served relative to cwd, as main() does
        cls.existing_runs = set(p.name for p in local_server.OUTPUTS_DIR.glob("run_*")) if local_server.OUTPUTS_DIR.exists() else set()
        cls.existing_uploads = set(p.name for p in local_server.UPLOADS_DIR.glob("*")) if local_server.UPLOADS_DIR.exists() else set()
        TCPServer.allow_reuse_address = True
        cls.server = TCPServer(("127.0.0.1", 0), QuietHandler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        # Disposable: remove only what this test created.
        if local_server.OUTPUTS_DIR.exists():
            for run in local_server.OUTPUTS_DIR.glob("run_*"):
                if run.name not in cls.existing_runs:
                    shutil.rmtree(run, ignore_errors=True)
            if not any(local_server.OUTPUTS_DIR.iterdir()):
                local_server.OUTPUTS_DIR.rmdir()
        if local_server.UPLOADS_DIR.exists():
            for upload in local_server.UPLOADS_DIR.glob("*"):
                if upload.name not in cls.existing_uploads:
                    upload.unlink()
            if not any(local_server.UPLOADS_DIR.iterdir()):
                local_server.UPLOADS_DIR.rmdir()
        os.chdir(cls.previous_cwd)

    # -- helpers
    def post(self, fields, files=()):
        body, ctype = multipart(fields, files)
        request = urllib.request.Request(
            self.base + "/generate", data=body, method="POST",
            headers={"Content-Type": ctype, "Content-Length": str(len(body))},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=30) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def run_dir_from(self, html):
        match = RUN_DIR_RE.search(html)
        return match.group(1) if match else None

    # -- tests
    def test_index_serves(self):
        status, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(b'name="layout"', body)

    def test_bundled_layout_generates_and_downloads_carry_checks(self):
        status, html = self.post({"layout": "mercer_layout.json"})
        self.assertEqual(status, 200)
        run_dir = self.run_dir_from(html)
        self.assertIsNotNone(run_dir, "success page must link the report")
        self.assertIn("All modelled checks passed.", html)
        self.assertIn("walkable path</strong>: unmeasured", html)

        status, raw = self.get(f"{run_dir}/space_plan_report.json")
        self.assertEqual(status, 200)
        report = json.loads(raw)
        self.assertEqual(report["checks"]["walkable_path"]["status"], "unmeasured")
        grouped = sorted({move["item"] for move in report["door_pass"]["moves"] if move.get("group")})
        self.assertEqual(grouped, ["Desk", "Desk Chair", "Dryer", "Washer"])
        self.assertEqual(report["door_pass"]["unresolved"], [])

        status, md = self.get(f"{run_dir}/space_plan_report.md")
        self.assertEqual(status, 200)
        self.assertIn("| walkable path | unmeasured |", md.decode())
        self.assertIn("| Desk | desk-set |", md.decode())
        self.assertIn("does not mean the layout is safe", md.decode())

        status, manifest = self.get(f"{run_dir}/manifest.json")
        self.assertEqual(json.loads(manifest)["space_plan_checks"]["walkable_path"], "unmeasured")
        for path in ("dimensioned_plan.svg", "mercer_model.obj", "sheets/G001_cover_sheet.svg", "drawing_set_print.html"):
            status, body = self.get(f"{run_dir}/{path}")
            self.assertEqual(status, 200, path)
            self.assertGreater(len(body), 0, path)
        status, cover = self.get(f"{run_dir}/sheets/G001_cover_sheet.svg")
        self.assertIn(b"Space plan checks", cover)
        self.assertNotIn(b"Space plan score", cover)
        status, viewer = self.get(f"/viewer?obj={run_dir}/mercer_model.obj&mtl={run_dir}/mercer_model.mtl")
        self.assertEqual(status, 200)

    def test_two_submissions_get_distinct_run_folders(self):
        _status, first = self.post({"layout": "samples/rect_two_room_layout.json"})
        _status, second = self.post({"layout": "samples/rect_two_room_layout.json"})
        self.assertNotEqual(self.run_dir_from(first), self.run_dir_from(second))

    def test_unresolved_group_is_visible_on_success_page_and_report(self):
        status, html = self.post({"layout": "samples/infeasible_group_layout.json"})
        self.assertEqual(status, 200)
        self.assertIn("modelled violation(s) found", html)
        self.assertIn("Unresolved:</strong> Desk + Desk Chair", html)
        status, md = self.get(f"{self.run_dir_from(html)}/space_plan_report.md")
        self.assertIn("UNRESOLVED: Desk + Desk Chair", md.decode())
        self.assertIn("| door clearance | fail |", md.decode())

    def test_invalid_layout_is_a_400_with_a_readable_message_and_no_run_folder(self):
        before = set(local_server.OUTPUTS_DIR.glob("run_*")) if local_server.OUTPUTS_DIR.exists() else set()
        status, html = self.post({"layout": "samples/adversarial_invalid_layout.json"})
        self.assertEqual(status, 400)
        self.assertIn("Generation failed: Zone", html)
        self.assertIn("extends outside the unit shell", html)
        self.assertIsNone(self.run_dir_from(html))
        after = set(local_server.OUTPUTS_DIR.glob("run_*")) if local_server.OUTPUTS_DIR.exists() else set()
        self.assertEqual(before, after, "a failed request must not leave a run folder")

    def test_missing_and_non_json_layouts_are_readable_400s(self):
        status, html = self.post({"layout": "does_not_exist.json"})
        self.assertEqual(status, 400)
        self.assertIn("Layout file not found: does_not_exist.json", html)
        status, html = self.post({"layout": "README.md"})
        self.assertEqual(status, 400)
        self.assertIn("Layout file is not valid JSON: README.md", html)

    def test_layout_path_outside_workspace_is_refused(self):
        status, html = self.post({"layout": "../../etc/hostname"})
        self.assertEqual(status, 400)
        self.assertIn("inside the workspace", html)

    def test_unreadable_style_image_is_reported_not_silently_ignored(self):
        status, html = self.post(
            {"layout": "samples/rect_two_room_layout.json"},
            [("style_images", "notanimage.jpg", b"this is not an image", "image/jpeg")],
        )
        self.assertEqual(status, 200)
        self.assertIn("Style images:</strong> 1 file(s) uploaded but not used", html)


if __name__ == "__main__":
    unittest.main()
