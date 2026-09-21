# Checkpoint INTERIOR-20260920-04: local web flow end to end

Date: 2026-09-20. Writer: Claude Code (sole primary). Builds on 46f741b (accepted).

Scope: the existing local web flow, driven over real HTTP on loopback in this
environment with the bundled synthetic layouts. No remote binding, no public
deployment, no photos, no outreach, no spend. Fix only defects the flow demonstrated.

## Reproducible commands

```bash
# terminal 1 (loopback, disposable outputs under ./outputs, gitignored)
HOST=127.0.0.1 PORT=8765 python3 local_server.py

# terminal 2: drive the form the way a browser would and print what comes back
python3 docs/validation/2026-09-20-web-flow/e2e_drive.py http://127.0.0.1:8765

# or, self-contained (ephemeral port, removes the run folders and uploads it created)
python3 -m unittest tests.test_local_server_e2e -v

# cleanup after the manual run
rm -rf outputs uploads
```

## What the flow did before fixes (`http_results_before_fixes.txt`, commit 46f741b)

| Case | Actual result |
| --- | --- |
| Submit bundled Mercer layout | HTTP 200; report, manifest, plan SVG, OBJ, cover sheet, print set all served (200). Report carried the grouped moves (Desk, Desk Chair, Washer, Dryer), 0 unresolved, `walkable path | unmeasured`, disclaimer. Cover sheet printed check statuses, no score. |
| Submit infeasible-group sample | HTTP 200; report had `UNRESOLVED: Desk + Desk Chair` and `door clearance | fail`; **success page said nothing about it** |
| Submit adversarial invalid layout | **HTTP 200** with "Generation failed: Zone 'Annex' extends outside the unit shell." on the form page |
| Missing layout path | **HTTP 200**, "Layout file not found: does_not_exist.json" |
| Non-JSON layout path (README.md) | **HTTP 200**, "Expecting value: line 1 column 1 (char 0)" (not understandable) |
| Garbage bytes as a style image | HTTP 200, file saved to `uploads/`, palette silently defaulted; only a server-side print ("Pillow not installed") |
| Four successful submissions within one second | **All wrote to the same `outputs/run_20260920_210503/`, each overwriting the last** |
| Default bind | `0.0.0.0` (all interfaces) with a free-text file path field |

## Fixes (demonstrated defects only)

1. Run folder is `run_<timestamp>_<6 hex>` created with exclusive mkdir; concurrent
   or same-second submissions no longer collide. Failed requests remove their empty
   run folder.
2. Generation failures return HTTP 400 (layout/validation problems) or 500
   (unexpected), with the message HTML-escaped. Success stays 200.
3. `load_layout` raises "Layout file is not valid JSON: <path> (line, column)" and
   "Layout file not found: <path>"; the server reports paths relative to the workspace.
4. Layout path must resolve inside the workspace (`../../etc/hostname` → 400).
5. Success page now shows each check's status, any unresolved group, the disclaimer,
   and whether uploaded style images were actually used (manifest gains
   `palette_from_images`).
6. Default `HOST` is `127.0.0.1`; `HOST=0.0.0.0` still works if someone insists.

## After fixes (`http_results_after_fixes.txt`)

| Case | Actual result |
| --- | --- |
| Mercer | 200; downloads unchanged and still carry group moves, 0 unresolved, walkable path unmeasured |
| Infeasible group | 200; success page shows "1 modelled violation(s) found", `Unresolved: Desk + Desk Chair`, and the report line |
| Adversarial | **400**, "Generation failed: Zone 'Annex' extends outside the unit shell.", no run folder |
| Missing file | **400**, "Layout file not found: does_not_exist.json" |
| Non-JSON | **400**, "Layout file is not valid JSON: README.md (line 1, column 1)" |
| Path outside workspace | **400**, "Layout path must be a file inside the workspace" |
| Garbage style image | 200 with "Style images: 1 file(s) uploaded but not used: Pillow is not installed or the files are not readable images." |
| Four submissions in one second | four distinct run folders |

Automated: `tests/test_local_server_e2e.py`, 8 cases, all pass; whole suite 43 tests.

## Findings not fixed here (not flow defects)

- With `pets=dog` and `lighting=mixed`, the Mercer run reports `overlap: fail`
  (Floor Lamp overlaps Dog Bed): preference pieces are centred without checking
  existing furniture. The web flow now surfaces it on the success page, which is the
  point of this checkpoint; the placement rule is a geometry task for a later slice.
- Pillow is not installed in this environment, so image-driven palettes were not
  exercised; the flow degrades to the default palette and now says so.
- The 3D viewer page was fetched (200) but not rendered in a browser; it loads
  three.js from a CDN, so it needs network in the user's browser.
- No authentication, rate limiting, or upload size limits: fine for loopback, not
  for anything else. Uploaded style images are written to `uploads/` by basename.

## Readiness note (retained)

Minimum real-space input for a first personal run: the room outline as a polygon in
feet, each door's wall, offset, width and swing room, each window's wall, offset and
width, and any fixed built-ins as boxes. Photos are not needed for the checks. Real-
space and customer validation remain absent; nothing here changes the Sep 18 baseline
of 0 users / 0 paying, or the Dec 17 target (one usable own-space design, 3 paying
customers, price undecided, $0 development spend).

## Follow-up INTERIOR-20260920-05 (2026-09-21): Windows URL separators

PM's Windows run of f722946 (Python 3.13) failed 3 of the 8 web-flow cases: the success
page interpolated `Path` objects into hrefs, so on Windows links read
`/outputs\run_...\space_plan_report.md`, the report regex found nothing, and the
follow-on requests were built from `None`. Linux never showed it because `str(Path)`
happens to use `/` there.

Fix: `local_server.output_url(out_dir, *parts)` builds every URL from `Path.parts`
joined with `/` and percent-encoded per component; `viewer_url_for` does the same for
the OBJ/MTL query. All 22 success-page links (including nested `sheets/*.svg`) and
the viewer query go through it. No filesystem path is ever formatted into a URL.

Verification without a Windows box: `OutputUrlTests` feed `PureWindowsPath`
(`C:\Users\...`) and `PurePosixPath` bases through the same helpers and assert
identical forward-slash output and no backslash anywhere. The live e2e test now
extracts every `href` on the success page, asserts none contains a backslash, and
downloads each one over HTTP expecting 200 (nested sheets, OBJ/MTL viewer included).
The report regex was not loosened; a missing link now fails with a named assertion
instead of a `None` URL. Suite: 46 tests, all pass on Linux. Windows confirmation is
the PM's rerun.
