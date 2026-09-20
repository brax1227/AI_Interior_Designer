#!/usr/bin/env python3
from __future__ import annotations

import html as html_lib
import json
import os
import shutil
import uuid
from datetime import datetime
from email.parser import BytesParser
from email.policy import default
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from socketserver import TCPServer
from typing import Dict, List, Tuple
from urllib.parse import parse_qs, quote, urlparse

from design_agent import run_design


BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUTS_DIR = BASE_DIR / "outputs"


def render_index(message: str | None = None) -> str:
    alert = (
        f'<div class="alert"><div class="alert-title">Latest Run</div><div>{message}</div></div>'
        if message
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Dream Home Design Studio</title>
  <style>
    :root {{
      --bg: #f6f3ee;
      --panel: rgba(255, 255, 255, 0.82);
      --panel-strong: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --line: rgba(148, 163, 184, 0.25);
      --accent: #9a6b43;
      --accent-strong: #7c5432;
      --accent-soft: rgba(154, 107, 67, 0.12);
      --success-soft: rgba(16, 185, 129, 0.12);
      --shadow: 0 20px 60px rgba(15, 23, 42, 0.10);
      --radius: 24px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(254, 240, 219, 0.9), transparent 32%),
        radial-gradient(circle at top right, rgba(220, 234, 245, 0.85), transparent 30%),
        linear-gradient(180deg, #fbfaf8 0%, var(--bg) 100%);
    }}
    a {{
      color: var(--accent-strong);
      text-decoration: none;
    }}
    a:hover {{ text-decoration: underline; }}
    .page {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 24px;
      align-items: stretch;
      margin-bottom: 24px;
    }}
    .hero-card, .panel {{
      background: var(--panel);
      backdrop-filter: blur(18px);
      border: 1px solid rgba(255, 255, 255, 0.65);
      box-shadow: var(--shadow);
      border-radius: var(--radius);
    }}
    .hero-card {{
      padding: 32px;
      min-height: 260px;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--accent-strong);
      background: var(--accent-soft);
      padding: 10px 14px;
      border-radius: 999px;
      margin-bottom: 18px;
    }}
    h1 {{
      font-size: clamp(2.2rem, 5vw, 4rem);
      line-height: 1.02;
      margin: 0 0 16px;
      max-width: 10ch;
    }}
    .hero-copy {{
      color: var(--muted);
      font-size: 1rem;
      line-height: 1.7;
      max-width: 62ch;
      margin: 0 0 24px;
    }}
    .hero-points {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }}
    .point {{
      background: rgba(255, 255, 255, 0.72);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
    }}
    .point strong {{
      display: block;
      font-size: 0.95rem;
      margin-bottom: 6px;
    }}
    .point span {{
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.5;
    }}
    .side-card {{
      padding: 24px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 18px;
    }}
    .side-title {{
      font-size: 1.05rem;
      font-weight: 700;
      margin: 0;
    }}
    .side-copy {{
      margin: 0;
      color: var(--muted);
      line-height: 1.65;
    }}
    .checklist {{
      display: grid;
      gap: 12px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}
    .checklist li {{
      display: flex;
      gap: 10px;
      align-items: flex-start;
      color: var(--text);
      line-height: 1.5;
    }}
    .check {{
      width: 22px;
      height: 22px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent-strong);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
      font-size: 13px;
      font-weight: 700;
    }}
    .alert {{
      margin-bottom: 22px;
      padding: 18px 20px;
      border-radius: 20px;
      background: var(--success-soft);
      border: 1px solid rgba(16, 185, 129, 0.16);
      box-shadow: 0 10px 30px rgba(16, 185, 129, 0.08);
      line-height: 1.6;
    }}
    .alert-title {{
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #047857;
      margin-bottom: 6px;
      font-weight: 700;
    }}
    .layout {{
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 24px;
      align-items: start;
    }}
    .panel {{
      padding: 28px;
    }}
    .panel-title {{
      margin: 0 0 6px;
      font-size: 1.35rem;
    }}
    .panel-copy {{
      margin: 0 0 24px;
      color: var(--muted);
      line-height: 1.65;
    }}
    .section-label {{
      margin: 24px 0 10px;
      font-size: 0.8rem;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--accent-strong);
      font-weight: 700;
    }}
    .grid {{
      display: grid;
      gap: 16px;
    }}
    .grid.two {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    label {{
      display: block;
      margin: 0 0 8px;
      font-weight: 700;
      font-size: 0.95rem;
    }}
    .field {{
      margin-bottom: 16px;
    }}
    input, textarea, select {{
      width: 100%;
      padding: 14px 16px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.85);
      color: var(--text);
      font-size: 0.98rem;
      outline: none;
      transition: border-color 140ms ease, box-shadow 140ms ease, transform 140ms ease;
    }}
    input:focus, textarea:focus, select:focus {{
      border-color: rgba(154, 107, 67, 0.55);
      box-shadow: 0 0 0 5px rgba(154, 107, 67, 0.12);
      transform: translateY(-1px);
    }}
    input[type="file"] {{
      padding: 12px;
      background: rgba(255, 255, 255, 0.65);
    }}
    .hint {{
      color: var(--muted);
      font-size: 0.9rem;
      line-height: 1.55;
      margin-top: 8px;
    }}
    .submit {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      margin-top: 10px;
      padding: 15px 22px;
      border: none;
      border-radius: 999px;
      background: linear-gradient(135deg, var(--accent) 0%, var(--accent-strong) 100%);
      color: #fff;
      font-size: 0.98rem;
      font-weight: 700;
      cursor: pointer;
      box-shadow: 0 18px 35px rgba(124, 84, 50, 0.24);
    }}
    .submit:hover {{
      transform: translateY(-1px);
    }}
    .sidebar-block + .sidebar-block {{
      margin-top: 18px;
    }}
    .info-card {{
      padding: 18px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.72);
      border: 1px solid var(--line);
    }}
    .info-card h3 {{
      margin: 0 0 8px;
      font-size: 1rem;
    }}
    .info-card p, .info-card li {{
      color: var(--muted);
      line-height: 1.6;
      margin: 0;
    }}
    .info-card ul {{
      margin: 10px 0 0;
      padding-left: 18px;
    }}
    .footer-note {{
      margin-top: 20px;
      color: var(--muted);
      font-size: 0.92rem;
      text-align: center;
    }}
    @media (max-width: 960px) {{
      .hero,
      .layout,
      .hero-points,
      .grid.two {{
        grid-template-columns: 1fr;
      }}
      .hero-card {{
        min-height: auto;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div class="hero-card">
        <div class="eyebrow">Interior Design Agent</div>
        <h1>Design your next home with a clearer vision.</h1>
        <p class="hero-copy">
          Upload your plan, define your style, and generate a concept package with a 3D model,
          shopping list, and space-planning guidance for your Mercer apartment.
        </p>
        <div class="hero-points">
          <div class="point">
            <strong>Visualize</strong>
            <span>Generate a room-by-room concept and interactive 3D preview.</span>
          </div>
          <div class="point">
            <strong>Personalize</strong>
            <span>Shape the layout around your style, budget, pets, and work needs.</span>
          </div>
          <div class="point">
            <strong>Plan</strong>
            <span>Get a shopping list and layout feedback before you move in.</span>
          </div>
        </div>
      </div>
      <div class="hero-card side-card">
        <div>
          <h2 class="side-title">What this creates</h2>
          <p class="side-copy">
            Each run produces a concept set built around your answers and floor plan assumptions.
          </p>
        </div>
        <ul class="checklist">
          <li><span class="check">1</span><span>Furnished 3D massing model with doors and windows</span></li>
          <li><span class="check">2</span><span>Shopping list aligned to style and budget direction</span></li>
          <li><span class="check">3</span><span>Design brief plus space-planning report</span></li>
        </ul>
      </div>
    </section>
    {alert}
    <section class="layout">
      <div class="panel">
        <h2 class="panel-title">Start a New Concept</h2>
        <p class="panel-copy">
          Fill in a few design details so the agent can build a stronger recommendation set.
        </p>
        <form action="/generate" method="post" enctype="multipart/form-data">
          <div class="section-label">Project Setup</div>
          <div class="field">
            <label>Layout JSON path</label>
            <input name="layout" value="mercer_layout.json" />
            <div class="hint">Use the sample Mercer layout or point to another layout JSON in this workspace.</div>
          </div>

          <div class="section-label">Style Direction</div>
          <div class="grid two">
            <div class="field">
              <label>Style keywords</label>
              <input name="style_keywords" value="modern cozy" />
            </div>
            <div class="field">
              <label>Color vibe</label>
              <input name="palette_preference" value="warm neutrals" />
            </div>
          </div>

          <div class="section-label">Lifestyle</div>
          <div class="grid two">
            <div class="field">
              <label>Budget</label>
              <select name="budget_level">
                <option value="low">low</option>
                <option value="mid" selected>mid</option>
                <option value="high">high</option>
              </select>
            </div>
            <div class="field">
              <label>Work from home?</label>
              <select name="work_from_home">
                <option value="yes" selected>yes</option>
                <option value="no">no</option>
              </select>
            </div>
            <div class="field">
              <label>Pets</label>
              <select name="pets">
                <option value="none" selected>none</option>
                <option value="cat">cat</option>
                <option value="dog">dog</option>
              </select>
            </div>
            <div class="field">
              <label>Lighting vibe</label>
              <select name="lighting_pref">
                <option value="mixed" selected>mixed</option>
                <option value="bright">bright</option>
                <option value="soft">soft</option>
              </select>
            </div>
          </div>

          <div class="section-label">Functionality</div>
          <div class="grid two">
            <div class="field">
              <label>Storage priority</label>
              <select name="storage_priority">
                <option value="low">low</option>
                <option value="medium" selected>medium</option>
                <option value="high">high</option>
              </select>
            </div>
            <div class="field">
              <label>Must-have items</label>
              <input name="must_have" value="none" />
            </div>
          </div>

          <div class="field">
            <label>Style images</label>
            <input name="style_images" type="file" multiple />
            <div class="hint">Upload inspiration images for colors and mood. Leave blank if you only want to work from text prompts.</div>
          </div>

          <button class="submit" type="submit">Generate My Concept</button>
        </form>
      </div>

      <div class="panel">
        <div class="sidebar-block">
          <h2 class="panel-title">Design Notes</h2>
          <p class="panel-copy">
            The better the intent you give the system, the more useful the concept becomes.
          </p>
        </div>
        <div class="sidebar-block info-card">
          <h3>Best style prompts</h3>
          <p>Try combinations like <code>japandi warm minimal</code>, <code>organic modern</code>, or <code>soft contemporary</code>.</p>
        </div>
        <div class="sidebar-block info-card">
          <h3>Helpful must-haves</h3>
          <ul>
            <li>entry bench</li>
            <li>reading nook</li>
            <li>large rug</li>
            <li>wine storage</li>
            <li>standing desk</li>
          </ul>
        </div>
        <div class="sidebar-block info-card">
          <h3>Current deliverables</h3>
          <ul>
            <li>3D model preview</li>
            <li>shopping list CSV + JSON</li>
            <li>design brief</li>
            <li>space-planning report</li>
          </ul>
        </div>
      </div>
    </section>
    <div class="footer-note">Built for local concept exploration of your future apartment layout.</div>
  </div>
</body>
</html>
"""


def render_success_page(
    output_dir: str,
    manifest_url: str,
    design_brief_url: str,
    report_url: str,
    renovation_url: str,
    renovation_schedule_url: str,
    finish_schedule_url: str,
    room_schedule_url: str,
    wall_schedule_url: str,
    opening_schedule_url: str,
    cabinet_schedule_url: str,
    dimensioned_plan_url: str,
    construction_sheet_url: str,
    spec_package_url: str,
    sheet_index_url: str,
    cover_sheet_url: str,
    plan_sheet_url: str,
    elevations_sheet_url: str,
    room_elevations_sheet_url: str,
    notes_sheet_url: str,
    drawing_set_print_url: str,
    viewer_url: str,
    checks_html: str = "",
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Concept Ready</title>
  <style>
    :root {{
      --bg: #f6f3ee;
      --text: #1f2937;
      --muted: #6b7280;
      --accent: #9a6b43;
      --accent-strong: #7c5432;
      --panel: rgba(255,255,255,0.9);
      --line: rgba(148,163,184,0.22);
      --shadow: 0 20px 60px rgba(15,23,42,0.10);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(254, 240, 219, 0.9), transparent 32%),
        radial-gradient(circle at top right, rgba(220, 234, 245, 0.85), transparent 30%),
        linear-gradient(180deg, #fbfaf8 0%, var(--bg) 100%);
    }}
    .page {{
      max-width: 980px;
      margin: 0 auto;
      padding: 36px 20px 56px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid rgba(255,255,255,0.6);
      border-radius: 28px;
      box-shadow: var(--shadow);
      padding: 32px;
    }}
    .eyebrow {{
      display: inline-block;
      padding: 10px 14px;
      border-radius: 999px;
      background: rgba(16,185,129,0.12);
      color: #047857;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 16px;
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: clamp(2rem, 5vw, 3.4rem);
      line-height: 1.04;
    }}
    p {{
      color: var(--muted);
      line-height: 1.7;
      margin: 0;
    }}
    .actions {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      margin-top: 28px;
    }}
    .action {{
      display: block;
      padding: 18px 18px;
      border-radius: 20px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.78);
      text-decoration: none;
      color: var(--text);
    }}
    .action strong {{
      display: block;
      margin-bottom: 6px;
      font-size: 1rem;
    }}
    .action span {{
      color: var(--muted);
      line-height: 1.5;
      font-size: 0.95rem;
    }}
    .primary {{
      background: linear-gradient(135deg, var(--accent) 0%, var(--accent-strong) 100%);
      color: white;
      border: none;
      box-shadow: 0 16px 30px rgba(124, 84, 50, 0.24);
    }}
    .primary span {{
      color: rgba(255,255,255,0.85);
    }}
    .meta {{
      margin-top: 22px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
      font-size: 0.95rem;
      color: var(--muted);
    }}
    .back {{
      display: inline-block;
      margin-top: 20px;
      color: var(--accent-strong);
      text-decoration: none;
      font-weight: 700;
    }}
    @media (max-width: 760px) {{
      .actions {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="card">
      <div class="eyebrow">Concept Generated</div>
      <h1>Your design package is ready.</h1>
      <p>
        The agent created a new concept run with your latest inputs. Use the links below to review
        the 3D model, design brief, shopping outputs, and planning report.
      </p>
      {checks_html}
      <div class="actions">
        <a class="action primary" href="{viewer_url}">
          <strong>Open 3D Viewer</strong>
          <span>Preview the current apartment concept in browser.</span>
        </a>
        <a class="action" href="{design_brief_url}">
          <strong>Read Design Brief</strong>
          <span>See the design direction, palette, and room-by-room notes.</span>
        </a>
        <a class="action" href="{report_url}">
          <strong>Open Space Plan Report</strong>
          <span>Review layout fit, overlap checks, and room stats.</span>
        </a>
        <a class="action" href="{renovation_url}">
          <strong>Open Renovation Package</strong>
          <span>Review finishes, renovation scope, and room-by-room upgrade direction.</span>
        </a>
        <a class="action" href="{renovation_schedule_url}">
          <strong>Open Renovation Schedule</strong>
          <span>See modeled components, trades, and installed cost ranges.</span>
        </a>
        <a class="action" href="{finish_schedule_url}">
          <strong>Open Finish Schedule</strong>
          <span>Review wall, floor, trim, and countertop finish systems by room.</span>
        </a>
        <a class="action" href="{room_schedule_url}">
          <strong>Open Room Schedule</strong>
          <span>Review room types, widths, depths, and approximate areas.</span>
        </a>
        <a class="action" href="{wall_schedule_url}">
          <strong>Open Wall Schedule</strong>
          <span>Review wall lengths, interior/exterior type, and opening counts.</span>
        </a>
        <a class="action" href="{opening_schedule_url}">
          <strong>Open Opening Schedule</strong>
          <span>Review current door and window widths and references.</span>
        </a>
        <a class="action" href="{cabinet_schedule_url}">
          <strong>Open Cabinet Schedule</strong>
          <span>Review modeled cabinetry and built-in storage components.</span>
        </a>
        <a class="action" href="{dimensioned_plan_url}">
          <strong>Open Dimensioned Plan</strong>
          <span>View the annotated 2D plan with room measurements.</span>
        </a>
        <a class="action" href="{construction_sheet_url}">
          <strong>Open Construction Sheet</strong>
          <span>Review the title block, keyed tags, general notes, and wall legend.</span>
        </a>
        <a class="action" href="{spec_package_url}">
          <strong>Open Spec Package</strong>
          <span>Read assumptions, general notes, and conceptual wall type definitions.</span>
        </a>
        <a class="action" href="{sheet_index_url}">
          <strong>Open Drawing Set Index</strong>
          <span>Review the multi-sheet package structure and sheet descriptions.</span>
        </a>
        <a class="action" href="{cover_sheet_url}">
          <strong>Open Cover Sheet</strong>
          <span>See project metadata, issue info, and drawing set summary.</span>
        </a>
        <a class="action" href="{plan_sheet_url}">
          <strong>Open Plan Sheet</strong>
          <span>Review the tagged plan sheet with title block and keyed note callouts.</span>
        </a>
        <a class="action" href="{elevations_sheet_url}">
          <strong>Open Elevation Sheet</strong>
          <span>Review E-series cabinet and built-in elevation views tied to the plan references.</span>
        </a>
        <a class="action" href="{room_elevations_sheet_url}">
          <strong>Open Grouped Elevations</strong>
          <span>Review room-based elevation compositions with cabinetry, fixtures, and appliances.</span>
        </a>
        <a class="action" href="{notes_sheet_url}">
          <strong>Open Notes Sheet</strong>
          <span>Review general notes, keyed notes, legend, and schedule references.</span>
        </a>
        <a class="action" href="{drawing_set_print_url}">
          <strong>Open Print Package</strong>
          <span>Open the full drawing set in one browser-friendly print layout.</span>
        </a>
        <a class="action" href="{manifest_url}">
          <strong>Open Manifest</strong>
          <span>Inspect every output path created for this run.</span>
        </a>
        <a class="action" href="{output_dir}">
          <strong>Browse Output Folder</strong>
          <span>Access OBJ, MTL, shopping list, and all generated files.</span>
        </a>
        <a class="action" href="/">
          <strong>Create Another Concept</strong>
          <span>Go back and generate a new version with different answers.</span>
        </a>
      </div>
      <div class="meta">Output folder: <code>{output_dir}</code></div>
      <a class="back" href="/">Back to studio</a>
    </div>
  </div>
</body>
</html>
"""


def render_viewer(obj_url: str, mtl_url: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>3D Viewer</title>
  <style>
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, sans-serif;
      background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
      color: #111827;
    }}
    #viewer {{ width: 100vw; height: 100vh; }}
    #toolbar {{
      position: absolute;
      top: 16px;
      left: 16px;
      display: flex;
      gap: 12px;
      align-items: center;
      padding: 12px 14px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.9);
      box-shadow: 0 18px 40px rgba(15, 23, 42, 0.12);
      backdrop-filter: blur(14px);
      z-index: 2;
    }}
    #toolbar .title {{
      font-weight: 700;
    }}
    #toolbar .meta {{
      color: #6b7280;
      font-size: 0.92rem;
    }}
    #toolbar a {{
      color: #7c5432;
      text-decoration: none;
      font-weight: 600;
    }}
    #status {{
      position: absolute;
      right: 16px;
      top: 16px;
      z-index: 2;
      padding: 12px 14px;
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.92);
      box-shadow: 0 18px 40px rgba(15, 23, 42, 0.12);
      color: #4b5563;
      max-width: 360px;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <div id="viewer"></div>
  <div id="toolbar">
    <a href="/">Back</a>
    <div>
      <div class="title">3D Concept Viewer</div>
      <div class="meta">Drag to orbit. Scroll to zoom. Shift + drag to pan.</div>
    </div>
  </div>
  <div id="status">Loading 3D model...</div>
  <script type="importmap">
    {{
      "imports": {{
        "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
        "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
      }}
    }}
  </script>
  <script type="module">
    import * as THREE from 'three';
    import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';
    import {{ MTLLoader }} from 'three/addons/loaders/MTLLoader.js';
    import {{ OBJLoader }} from 'three/addons/loaders/OBJLoader.js';

    const container = document.getElementById('viewer');
    const status = document.getElementById('status');
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf3f4f6);
    const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.set(30, 30, 30);

    const renderer = new THREE.WebGLRenderer({{ antialias: true }});
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(20, 3, 12);
    controls.enableDamping = true;
    controls.update();

    const light1 = new THREE.DirectionalLight(0xffffff, 1.2);
    light1.position.set(20, 40, 20);
    scene.add(light1);
    const light2 = new THREE.DirectionalLight(0xfff7ed, 0.8);
    light2.position.set(-10, 25, -20);
    scene.add(light2);
    const light3 = new THREE.DirectionalLight(0xe0f2fe, 0.45);
    light3.position.set(10, 12, 35);
    scene.add(light3);
    scene.add(new THREE.AmbientLight(0xffffff, 0.95));

    const grid = new THREE.GridHelper(80, 40, 0xd1d5db, 0xe5e7eb);
    grid.position.y = -0.02;
    scene.add(grid);

    const axes = new THREE.AxesHelper(5);
    axes.visible = false;
    scene.add(axes);

    function setStatus(message, isError = false) {{
      status.textContent = message;
      status.style.color = isError ? '#b91c1c' : '#4b5563';
      status.style.display = 'block';
    }}

    function frameObject(object) {{
      const box = new THREE.Box3().setFromObject(object);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z, 1);
      const fov = camera.fov * (Math.PI / 180);
      let cameraZ = Math.abs(maxDim / Math.sin(fov / 2));
      cameraZ *= 0.7;
      camera.position.set(center.x + maxDim * 0.55, center.y + maxDim * 1.15, center.z + cameraZ * 0.7);
      controls.target.copy(center);
      controls.update();
    }}

    const mtlLoader = new MTLLoader();
    mtlLoader.load(
      '{mtl_url}',
      (materials) => {{
        materials.preload();
        const objLoader = new OBJLoader();
        objLoader.setMaterials(materials);
        objLoader.load(
          '{obj_url}',
          (obj) => {{
            obj.traverse((child) => {{
              if (!child.isMesh || !child.material) return;
              const materialName = child.material.name || '';
              if (materialName === 'walls') {{
                child.material.transparent = true;
                child.material.opacity = 0.42;
              }}
              if (materialName.startsWith('floor_')) {{
                child.material.opacity = 1.0;
              }}
              child.castShadow = false;
              child.receiveShadow = true;
            }});
            scene.add(obj);
            frameObject(obj);
            setStatus('Model loaded successfully.');
            setTimeout(() => {{
              status.style.display = 'none';
            }}, 1800);
          }},
          () => {{
            setStatus('Loading geometry...');
          }},
          (error) => {{
            console.error(error);
            setStatus('Could not load OBJ model. Check the generated files and try again.', true);
          }}
        );
      }},
      () => {{
        setStatus('Loading materials...');
      }},
      (error) => {{
        console.error(error);
        setStatus('Could not load MTL materials. The viewer scripts may be blocked or the file path may be invalid.', true);
      }}
    );

    window.addEventListener('resize', () => {{
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    }});

    function animate() {{
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }}
    animate();
  </script>
</body>
</html>
"""


def parse_form(handler: SimpleHTTPRequestHandler) -> Tuple[Dict[str, str], List[Tuple[str, str, bytes]]]:
    content_type = handler.headers.get("Content-Type", "")
    content_length = int(handler.headers.get("Content-Length", "0"))
    body = handler.rfile.read(content_length)

    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=default).parsebytes(header + body)

    fields: Dict[str, str] = {}
    files: List[Tuple[str, str, bytes]] = []

    for part in message.iter_parts():
        disposition = part.get("Content-Disposition", "")
        if not disposition:
            continue
        params = dict(part.get_params(header="content-disposition"))
        name = params.get("name")
        if not name:
            continue
        filename = params.get("filename")
        payload = part.get_payload(decode=True) or b""
        if filename:
            files.append((name, filename, payload))
        else:
            fields[name] = payload.decode("utf-8", errors="ignore").strip()
    return fields, files


def save_uploads(files: List[Tuple[str, str, bytes]]) -> List[Path]:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []
    for field_name, filename, payload in files:
        if field_name != "style_images" or not filename:
            continue
        safe_name = os.path.basename(filename)
        dest = UPLOADS_DIR / safe_name
        with dest.open("wb") as handle:
            handle.write(payload)
        saved.append(dest)
    return saved


def build_answers(fields: Dict[str, str]) -> Dict:
    def value(name: str, default: str) -> str:
        if name in fields and fields[name].strip():
            return fields[name].strip()
        return default

    return {
        "style_keywords": value("style_keywords", "modern cozy"),
        "palette_preference": value("palette_preference", "warm neutrals"),
        "budget_level": value("budget_level", "mid"),
        "work_from_home": value("work_from_home", "yes"),
        "pets": value("pets", "none"),
        "lighting_pref": value("lighting_pref", "mixed"),
        "storage_priority": value("storage_priority", "medium"),
        "must_have": value("must_have", "none"),
    }


def resolve_layout_path(raw: str) -> Path:
    """Only layout files inside this workspace can be used; the form is a path, not an upload."""
    candidate = (BASE_DIR / (raw or "mercer_layout.json")).resolve()
    if BASE_DIR not in candidate.parents:
        raise ValueError(f"Layout path must be a file inside the workspace: {raw}")
    # Relative to the workspace (the server's working directory) so messages stay readable.
    return candidate.relative_to(BASE_DIR)


def new_run_dir() -> Path:
    """Unique per request: two submissions in the same second must not overwrite each other."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    while True:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = OUTPUTS_DIR / f"run_{stamp}_{uuid.uuid4().hex[:6]}"
        try:
            candidate.mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            continue
        return candidate


def render_checks_summary(report: Dict, style_note: str | None) -> str:
    checks = report.get("checks", {})
    rows = "".join(
        f"<li><strong>{name.replace('_', ' ')}</strong>: {check['status']}"
        + (f" ({check['finding_count']} finding(s))" if check.get("finding_count") else "")
        + "</li>"
        for name, check in checks.items()
    )
    unresolved = report.get("door_pass", {}).get("unresolved", [])
    unresolved_html = "".join(
        f"<li><strong>Unresolved:</strong> {' + '.join(entry['members'])} in {entry['room']} still blocks the {entry['door_room']} door.</li>"
        for entry in unresolved
    )
    style_html = f"<li><strong>Style images:</strong> {style_note}</li>" if style_note else ""
    violations = report.get("modelled_violation_count", 0)
    headline = (
        "All modelled checks passed." if not violations else f"{violations} modelled violation(s) found. Open the report before using this plan."
    )
    return (
        '<div class="checks" style="margin:0 0 20px;padding:14px 16px;border:1px solid #cbd5e1;border-radius:10px;background:#f8fafc;">'
        f"<p style=\"margin:0 0 8px;font-weight:600;\">{headline}</p>"
        f'<ul style="margin:0;padding-left:18px;">{rows}{unresolved_html}{style_html}</ul>'
        f'<p style="margin:8px 0 0;font-size:0.9em;color:#475569;">{report.get("disclaimer", "")}</p>'
        "</div>"
    )


class DesignHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/" or self.path.startswith("/index"):
            page = render_index()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(page.encode("utf-8"))
            return
        if self.path.startswith("/viewer"):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            obj_url = params.get("obj", [""])[0]
            mtl_url = params.get("mtl", [""])[0]
            if not obj_url or not mtl_url:
                self.send_error(400, "Missing obj or mtl query parameter.")
                return
            page = render_viewer(obj_url, mtl_url)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(page.encode("utf-8"))
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path != "/generate":
            self.send_error(404, "Not Found")
            return

        status = 200
        out_dir: Path | None = None
        try:
            fields, files = parse_form(self)
            answers = build_answers(fields)
            layout_path = resolve_layout_path(fields.get("layout", "mercer_layout.json"))
            style_images = save_uploads(files)

            out_dir = new_run_dir()
            manifest = run_design(layout_path, answers, style_images, out_dir)
            report = json.loads((out_dir / "space_plan_report.json").read_text(encoding="utf-8"))
            style_note = None
            if style_images:
                if not manifest.get("palette_from_images"):
                    style_note = (
                        f"{len(style_images)} file(s) uploaded but not used: Pillow is not installed or the files are not readable images. "
                        "The default palette was used."
                    )
                else:
                    style_note = f"{len(style_images)} file(s) used to infer the palette."

            obj_rel = out_dir.relative_to(BASE_DIR) / "mercer_model.obj"
            mtl_rel = out_dir.relative_to(BASE_DIR) / "mercer_model.mtl"
            viewer_url = (
                f"/viewer?obj={quote('/' + str(obj_rel))}&mtl={quote('/' + str(mtl_rel))}"
            )
            page = render_success_page(
                f"/{out_dir.relative_to(BASE_DIR)}",
                f"/{out_dir.relative_to(BASE_DIR) / 'manifest.json'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'design_brief.md'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'space_plan_report.md'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'renovation_package.md'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'renovation_schedule.md'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'finish_schedule.md'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'room_schedule.md'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'wall_schedule.md'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'opening_schedule.md'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'cabinet_schedule.md'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'dimensioned_plan.svg'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'construction_sheet.svg'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'spec_package.md'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'sheet_index.md'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'sheets' / 'G001_cover_sheet.svg'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'sheets' / 'A101_plan_sheet.svg'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'sheets' / 'A201_elevations_sheet.svg'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'sheets' / 'A202_room_elevations_sheet.svg'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'sheets' / 'A601_notes_sheet.svg'}",
                f"/{out_dir.relative_to(BASE_DIR) / 'drawing_set_print.html'}",
                viewer_url,
                render_checks_summary(report, style_note),
            )
        except (FileNotFoundError, ValueError, KeyError) as exc:
            status = 400
            page = render_index(f"Generation failed: {html_lib.escape(str(exc))}")
        except Exception as exc:  # unexpected: still tell the user, but flag it as a server error
            status = 500
            page = render_index(f"Generation failed (unexpected error): {type(exc).__name__}: {html_lib.escape(str(exc))}")
        if status != 200 and out_dir is not None and not (out_dir / "manifest.json").exists():
            shutil.rmtree(out_dir, ignore_errors=True)  # do not leave half-written run folders behind
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(page.encode("utf-8"))


def main() -> int:
    os.chdir(BASE_DIR)
    # Loopback only by default; this tool reads workspace files by path and is not hardened for remote use.
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"Serving on http://{host}:{port}")
    with TCPServer((host, port), DesignHandler) as httpd:
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
