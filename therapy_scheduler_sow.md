# Therapy Scheduler Pro — MVP Scope of Work & Build Plan

## Project Overview

**Client:** Therapy clinic currently managing scheduling via whiteboard  
**Problem:** Manual scheduling for ~38 therapists and ~35 clients with complex constraint rules (intensity limits, break requirements, travel buffers, workload caps). Custom GPT approach failed because GPT cannot reliably edit Excel or enforce all rules.  
**Solution:** Streamlit web app that replaces the whiteboard, reads/writes their Excel format, validates all scheduling rules automatically, and (Phase 2) uses Claude API to auto-generate optimal schedules.  
**Budget:** ~$2,000  
**Hosting:** Streamlit Community Cloud (free) or Vercel  
**Database:** Excel file (their existing format — no migration needed)

---

## Tech Stack

| Layer | Tool | Why |
|-------|------|-----|
| Frontend/App | Streamlit | Fastest path to editable tables, forms, file I/O |
| Data Layer | .xlsx via openpyxl + pandas | Client already uses Excel — zero migration friction |
| Validation Engine | Pure Python | No API cost, instant feedback, deterministic |
| AI Scheduling (Phase 2) | Anthropic Claude API (claude-sonnet-4-20250514) | Structured JSON output for schedule generation |
| Hosting | Streamlit Community Cloud | Free, connects to GitHub, auto-deploys on push |
| Version Control | GitHub (private repo) | Client can't accidentally break prod |

---

## Phase 1 — Core MVP (Week 1-2)

This is the $2K deliverable. No AI. Pure tool replacement for the whiteboard.

### 1.1 — Project Setup (Day 1)

- [ ] Init GitHub repo (`therapy-scheduler`)
- [ ] Create `requirements.txt`:
  ```
  streamlit
  pandas
  openpyxl
  ```
- [ ] Create base `app.py` with page config and navigation
- [ ] Create `/utils` folder for helper modules
- [ ] Create `/data` folder — drop their Excel file here as the default template
- [ ] Set up `.streamlit/config.toml` for theming (dark mode, brand colors)

**File structure:**
```
therapy-scheduler/
├── app.py                  # Main entry point + navigation
├── pages/
│   ├── 1_therapists.py     # Therapists tab
│   ├── 2_clients.py        # Clients tab
│   ├── 3_schedule.py       # Current Assignments tab
│   └── 4_validation.py     # Flags & violations dashboard
├── utils/
│   ├── data_manager.py     # Read/write Excel, session state management
│   ├── validators.py       # All constraint-checking logic
│   ├── time_helpers.py     # Time parsing, formatting, overlap detection
│   └── constants.py        # Column names, day mappings, color codes
├── data/
│   └── template.xlsx       # Default blank template matching client schema
├── requirements.txt
├── .streamlit/
│   └── config.toml
└── README.md
```

### 1.2 — Data Manager Module (Day 1-2)

`utils/data_manager.py` — This is the backbone. Everything reads/writes through here.

**Functions to build:**

- `load_workbook(file)` → Reads uploaded .xlsx, returns dict of DataFrames (`{"therapists": df, "clients": df, "assignments": df}`)
- `save_to_session(data_dict)` → Stores DataFrames in `st.session_state` so edits persist across page navigations
- `get_therapists()` → Returns therapists DataFrame from session state
- `get_clients()` → Returns clients DataFrame from session state
- `get_assignments()` → Returns assignments DataFrame from session state
- `update_therapists(df)` → Writes edited therapists back to session state
- `update_clients(df)` → Writes edited clients back to session state
- `update_assignments(df)` → Writes edited assignments back to session state
- `export_workbook()` → Converts session state DataFrames back to .xlsx BytesIO buffer for download

**Key decisions:**
- Use `st.session_state` as the in-memory store (survives page switches, lost on browser close)
- On first load, user uploads their Excel OR app loads the template
- Every edit triggers a session state update
- Export always rebuilds from session state (never mutates the original file)

### 1.3 — Time Helpers Module (Day 2)

`utils/time_helpers.py` — Parsing the messy time formats in their data.

**Functions to build:**

- `parse_time(time_str)` → Handles all their formats: "8am", "8:30am", "8:00 AM", "14:30" → returns minutes since midnight
- `format_time(minutes)` → minutes since midnight → "8:30 AM"
- `parse_days(day_str)` → Handles: "Mon-Fri", "Mon,Tue,Thu,Fri", "4 days (flexible)", "Mon - Sat" → returns list of day strings
- `parse_schedule(schedule_str)` → Handles complex schedules like "Mon Wed Fri 12pm-3pm, Tue Thu 12pm-5pm" → returns dict `{day: [(start, end), ...]}`
- `check_overlap(start1, end1, start2, end2)` → Returns bool
- `calculate_chain(sorted_blocks)` → Returns max continuous work chain in minutes (accounts for 30-min break resets)

**This module is critical.** Their data has inconsistent formatting (dashes, commas, spaces, AM/PM variations). Build robust parsing with fallbacks. Write tests for the edge cases:
- "Mon - Fri" vs "Mon-Fri" vs "Mon, Tue, Wed, Thu, Fri"
- "8am" vs "8:00 AM" vs "08:00"  
- "Mon 3pm-6pm, Tue 8am-6pm, Thu 8am-6pm, Fri 8am-6pm" (per-day schedules)

### 1.4 — Therapists Page (Day 2-3)

`pages/1_therapists.py`

**Layout:**
- Header with therapist count
- `st.data_editor` showing all therapists with editable columns:
  - Name (text)
  - Days Available (text)
  - Hours Available (text)
  - In-Home (selectbox: Yes/No)
  - Preferred Max Hours (number, nullable)
  - 40 Hour Eligible (selectbox: Yes/No)
  - Notes (text)
- "Add Therapist" button → appends empty row
- "Delete Selected" → removes checked rows
- Weekly hours summary per therapist (calculated from assignments)
- Color-coded utilization: green (<30h), yellow (30-35h), red (>35h)

### 1.5 — Clients Page (Day 3)

`pages/2_clients.py`

**Layout:**
- Header with client count + assigned/unassigned breakdown
- Filter toggles: All | Assigned | Unassigned
- `st.data_editor` with columns:
  - Name (text)
  - Schedule Needed (text)
  - Days (text)
  - In-Home (selectbox: Home/Clinic/Hybrid)
  - Travel Notes (text)
  - Intensity (selectbox: High/Low)
  - Notes (text)
- For each client, show assigned therapist(s) if any
- Unassigned clients highlighted with warning badge

### 1.6 — Schedule / Assignments Page (Day 3-5)

`pages/3_schedule.py` — This is the main page they'll live in.

**Two view modes:**

**Table View (default):**
- `st.data_editor` for Current Assignments with columns:
  - Client (selectbox populated from clients list)
  - Therapist (selectbox populated from therapists list)
  - Days (text)
  - Start (time)
  - End (time)
  - Location (selectbox: Clinic/Home/Hybrid)
  - Assignment Type (selectbox: Recurring/Float)
  - Notes (text)
- "Add Assignment" button
- "Delete Selected" button
- Inline validation — flag icon next to rows with violations

**Timeline View (stretch goal for Phase 1):**
- Day selector (Mon-Sat)
- Horizontal bar chart using `st.plotly_chart` or native Streamlit charting
- Each row = therapist, each block = client session
- Color-coded by client
- This is the "wow" view for demos — implement if time allows, skip if tight

### 1.7 — Validation Engine (Day 4-5)

`utils/validators.py` — Pure Python, no AI. This is the real value.

**Validation functions to build (each returns list of flag dicts):**

```python
# Flag format: {"type": "error"|"warning"|"critical", "msg": str, "therapist": str, "client": str}
```

- `check_overlaps(assignments_df)` → No therapist double-booked at same time
- `check_intensity_chains(assignments_df, clients_df)` → High intensity max 3h continuous, Low max 4h
- `check_break_rules(assignments_df)` → 30-min break required every 4h, must be real gap
- `check_travel_buffers(assignments_df)` → 30-min buffer between in-home sessions
- `check_workload_caps(assignments_df)` → Soft cap 30h (warning), hard cap 35h (error), 40h only if eligible
- `check_availability(assignments_df, therapists_df)` → Therapist not scheduled outside their available hours/days
- `check_in_home_capability(assignments_df, therapists_df)` → In-home assignments only to therapists who can travel
- `check_client_coverage(assignments_df, clients_df)` → Flag unassigned clients or partial coverage gaps
- `check_preferred_max(assignments_df, therapists_df)` → Flag when therapist exceeds their preferred max
- `check_forty_hour_break(assignments_df, therapists_df)` → If at 40h, must have 2h mid-day break
- `validate_all(assignments_df, therapists_df, clients_df)` → Runs all checks, returns sorted flags

### 1.8 — Validation Dashboard Page (Day 5)

`pages/4_validation.py`

**Layout:**
- Summary cards at top: X errors, Y warnings, Z critical
- Grouped by type (errors first, then critical, then warnings)
- Each flag shows: client, therapist, days, times, violation description
- "Run Validation" button (or auto-run on page load)
- Expandable sections per therapist showing all their flags

### 1.9 — Excel Import/Export (Day 5-6)

**Import flow:**
- Sidebar file uploader: `st.file_uploader("Upload Schedule", type=["xlsx"])`
- On upload: parse all 3 tabs, validate column names match expected schema
- If columns don't match: show mapping UI or error message
- Store parsed data in session state

**Export flow:**
- "Download Updated Schedule" button in sidebar (always visible)
- Rebuilds .xlsx from session state with all 3 tabs
- Preserves their column naming and order
- `st.download_button` with the BytesIO buffer

### 1.10 — Deploy to Streamlit Cloud (Day 6)

- [ ] Push repo to GitHub
- [ ] Connect Streamlit Community Cloud to repo
- [ ] Set `app.py` as entry point
- [ ] Test upload/edit/download/validate flow end-to-end
- [ ] Share URL with client for testing
- [ ] Write brief user guide (can be in the app sidebar or a README)

---

## Phase 2 — Claude AI Integration (Week 3-4, separate scope)

This is the upgrade pitch. Not included in the $2K but scoped here so you can quote it.

### 2.1 — Auto-Schedule Engine

- "Auto-Schedule Unassigned" button on the Schedule page
- On click: sends current therapists, clients, existing assignments, and full rule set to Claude API
- System prompt = their rules document (optimized for structured output)
- Claude returns JSON array of proposed assignments
- App validates Claude's output against the Python validation engine (never trust LLM blindly)
- Shows proposed assignments in a diff view: "Claude suggests these 12 new assignments"
- User can accept all, accept individual, or reject
- Accepted assignments merge into the assignments table

**Claude API call structure:**
```python
# System prompt: full rule set + output format instructions
# User message: JSON blob of current state
# Response: JSON array of {client, therapist, days, start, end, location, type, notes}
# Model: claude-sonnet-4-20250514 (fast + cheap for structured output)
# Max tokens: 4096
# Cost: ~$0.01-0.05 per schedule generation
```

### 2.2 — Chat Sidebar for Schedule Adjustments

- Collapsible chat panel on the right side
- User types natural language: "Move JoHa to afternoon with a different therapist"
- Claude receives current schedule state + the request
- Returns specific changes as structured JSON
- App shows proposed changes for approval before applying
- Conversation history maintained in session state

### 2.3 — Conflict Resolution Assistant

- When validation finds violations, user can click "Fix with AI" on any flag
- Claude receives the specific violation + surrounding context
- Suggests 2-3 resolution options
- User picks one, app applies the change

### 2.4 — Estimated Cost for Phase 2

- Development: ~$3,000-5,000 (15-25 hours)
- Ongoing API cost: ~$5-15/month (depends on usage frequency)
- Total value to client: they go from "tool" to "AI scheduling assistant"

---

## Constraint Rules Reference (from client's rule doc)

Embed this in `utils/constants.py` and reference throughout validation logic.

### Hard Constraints (errors — must never violate)
1. **No overlaps** — one therapist, one client at a time
2. **Block locking** — scheduled block = no other client in that slot
3. **Break every 4h** — 30-min minimum real gap (no client assigned)
4. **Chain logic** — continuous time across clients = one chain, max 4h
5. **Intensity caps** — High: 3h max continuous, Low: 4h max continuous
6. **Travel buffer** — 30-min between in-home sessions

### Soft Constraints (warnings — try to avoid)
7. **Workload soft cap** — 30h/week warning
8. **Workload hard cap** — 35h/week high warning
9. **40h rule** — only if eligible, requires 2h mid-day break
10. **Preferred max** — therapist-specific, can exceed if needed but flag it

### Scheduling Priority Order
1. Client coverage (all hours filled)
2. Therapist availability (respect their schedule)
3. Intensity rules
4. Travel constraints
5. Workload caps
6. Preferred max hours
7. Float usage
8. Continuity (minimize therapist switching)

### Data Formats to Handle
- Days: "Mon-Fri", "Mon, Tue, Thu, Fri", "4 days (flexible)", "Mon - Sat"
- Times: "8am", "8:00 AM", "3:30pm-5:30pm", "Mon 3pm-6pm, Tue 8am-6pm"
- Location: Home, Clinic, Hybrid (with day-specific notes)
- Roles: "Role: Float/Lead; Direct Target: X; Direct Max: Y" (in notes field)

---

## Deliverables Summary

### Phase 1 ($2,000)
| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | Deployed Streamlit app | Hosted on Streamlit Cloud, shareable URL |
| 2 | Therapists management page | View, add, edit, delete therapists |
| 3 | Clients management page | View, add, edit, delete clients with status |
| 4 | Schedule/Assignments page | Editable assignment table with inline validation |
| 5 | Validation dashboard | Real-time constraint checking across all 10+ rules |
| 6 | Excel import/export | Upload their .xlsx, download updated version |
| 7 | User guide | In-app instructions or README walkthrough |
| 8 | Training session | 30-min walkthrough with clinic staff |

### Phase 2 ($3,000-5,000 — quoted separately)
| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | Auto-schedule engine | Claude-powered assignment generation |
| 2 | Chat sidebar | Natural language schedule adjustments |
| 3 | Conflict resolution AI | AI-suggested fixes for violations |

---

## Timeline

```
Week 1
├── Day 1-2: Project setup, data manager, time helpers
├── Day 3-4: Therapists + Clients pages, Assignments page
└── Day 5:   Validation engine (all constraint checks)

Week 2
├── Day 1-2: Validation dashboard, Excel import/export
├── Day 3:   Polish, edge case testing, deploy to Streamlit Cloud
├── Day 4:   Client walkthrough + feedback
└── Day 5:   Bug fixes from feedback, final deploy
```

---

## Notes for AP

- **Don't overthink the UI.** Streamlit's default `st.data_editor` is good enough for MVP. The client is coming from a whiteboard — any table UI is a 10x improvement.
- **The validation engine is the real product.** That's what the GPT couldn't do. Nail the constraint logic and the rest is just presentation.
- **Test with their actual data first.** Load their Excel on day 1, make sure every weird time format parses correctly before building pages.
- **Phase 2 is where the margin is.** Phase 1 at $2K is basically a loss leader. Once they depend on the tool daily, the AI upgrade is an easy sell.
- **Keep the Excel as the source of truth for now.** Don't try to add a database in Phase 1. It adds complexity with zero value for the client at this stage.
