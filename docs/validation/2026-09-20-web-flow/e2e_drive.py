"""Drive the running local server over HTTP and record what actually comes back."""
import json, re, sys, urllib.request, urllib.error, uuid
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"

def multipart(fields, files=()):
    boundary = "----e2e" + uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    for name, filename, payload, ctype in files:
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\nContent-Type: {ctype}\r\n\r\n").encode() + payload + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"

def post(fields, files=()):
    body, ctype = multipart(fields, files)
    req = urllib.request.Request(BASE + "/generate", data=body, headers={"Content-Type": ctype, "Content-Length": str(len(body))}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def run_case(label, fields, files=()):
    status, html = post(fields, files)
    m = re.search(r'href="(/outputs/run_[0-9a-f_]+)/space_plan_report\.md"', html)
    err = re.search(r"Generation failed: ([^<]+)", html)
    print(f"\n== {label}: POST /generate -> HTTP {status}; run_dir={m.group(1) if m else None}; error={err.group(1).strip() if err else None}")
    return status, (m.group(1) if m else None), html

# 1. bundled Mercer layout
status, run_dir, html = run_case("mercer", {"layout": "mercer_layout.json", "storage_priority": "high", "pets": "dog"})
for path in ("space_plan_report.md", "space_plan_report.json", "manifest.json", "dimensioned_plan.svg", "mercer_model.obj", "sheets/G001_cover_sheet.svg", "drawing_set_print.html"):
    st, data = get(f"{run_dir}/{path}")
    print(f"   GET {run_dir}/{path} -> {st} {len(data)} bytes")
st, data = get(f"{run_dir}/space_plan_report.json")
rep = json.loads(data)
print("   checks:", {k: v["status"] for k, v in rep["checks"].items()})
print("   door_pass moves:", len(rep["door_pass"]["moves"]), "grouped:", sorted({m["item"] for m in rep["door_pass"]["moves"] if m.get("group")}), "unresolved:", len(rep["door_pass"]["unresolved"]))
st, md = get(f"{run_dir}/space_plan_report.md"); md = md.decode()
print("   md has 'walkable path | unmeasured':", "| walkable path | unmeasured |" in md, "| has desk-set row:", "| Desk | desk-set |" in md, "| has disclaimer:", "does not mean the layout is safe" in md)
st, man = get(f"{run_dir}/manifest.json"); man = json.loads(man)
print("   manifest space_plan_checks:", man.get("space_plan_checks"), "violations:", man.get("space_plan_modelled_violations"))
st, svg = get(f"{run_dir}/dimensioned_plan.svg"); print("   dimensioned_plan.svg dashed door zones:", svg.count(b'stroke-dasharray="4 3"'))
st, cover = get(f"{run_dir}/sheets/G001_cover_sheet.svg"); print("   cover sheet carries check line:", b"Space plan checks" in cover, "| old score text:", b"Space plan score" in cover)
st, viewer = get("/viewer?obj=" + run_dir + "/mercer_model.obj&mtl=" + run_dir + "/mercer_model.mtl"); print(f"   GET /viewer -> {st} {len(viewer)} bytes")

# 2. infeasible group sample: generation succeeds but report must show UNRESOLVED
status, run_dir, html = run_case("infeasible group sample", {"layout": "samples/infeasible_group_layout.json"})
st, md = get(f"{run_dir}/space_plan_report.md"); md = md.decode()
print("   md has UNRESOLVED line:", "UNRESOLVED: Desk + Desk Chair" in md, "| door clearance fail:", "| door clearance | fail |" in md)
print("   success page mentions failing checks or unresolved:", ("unresolved" in html.lower()), ("fail" in html.lower()))

# 3. adversarial invalid layout
run_case("adversarial invalid layout", {"layout": "samples/adversarial_invalid_layout.json"})
# 4. missing layout file
run_case("missing layout path", {"layout": "does_not_exist.json"})
# 5. layout path that is not JSON
run_case("non-JSON layout path", {"layout": "README.md"})
# 6. invalid style image upload (garbage bytes) with valid layout
status, run_dir, html = run_case("garbage style image upload", {"layout": "samples/rect_two_room_layout.json"}, [("style_images", "notanimage.jpg", b"this is not an image", "image/jpeg")])
# 7. empty form (defaults)
run_case("empty form", {})
