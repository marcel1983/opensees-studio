---
title: File → Export → Report (PDF / Word / HTML)
group: File
summary: A calculation report: the model, loads, cases and the results of this session.
see_also: file.export_ifc, design.steel_check, design.connections, design.chapter_j, display.select_results
order: 540
---

Writes one document that reads top to bottom like a calculation report. Choose
**PDF** (A4, printed by Qt, no browser needed), a **Word document** (.docx, to
edit and sign) or an **HTML page** (opens in any browser).

In Word the table of contents is a field: Word asks to update the fields when it
opens the file (answer Yes) and then fills in the page numbers; F9 on the
contents updates it after an edit. The header and footer carry the page number
as Word fields, so they stay right as the document is edited.

# The options window
Before the file name is asked, a window sets the layout and what goes in. The
choice is remembered for the next export.
- **Language** — English or Spanish. The headings, column names, notes and
  the header and footer are translated; names you gave (cases, patterns,
  sections, materials) and the solver's type names are printed as they are. A
  check added to the program later prints in English until it is translated.
- **Cover page** — the project block (name, description, author, company, date,
  units, program and the revisions) on a page of its own.
- **Drawing of the structure on the cover** — the members, area elements and
  supports in isometric view (from +X, -Y, +Z, Z up), or in elevation for a 2D
  model. It is drawn from the model, not from the viewport, so the zoom and the
  display options do not change it.
- **Table of contents** — every chapter and subsection; in the PDF with the page
  it starts on, in the HTML page as links.
- **Number chapters and subsections** — 1, 2, … and 1.1, 1.2, …, in the
  headings and in the contents.
- **Start every chapter on a new page** — off by default, so short chapters
  share a page.
- **Header and footer (PDF, Word)** — the project name, company and author at the
  top; the program, the date and *Page N of M* at the bottom. The cover has
  neither.
- **Keep tables on one page (PDF, Word)** — a table that would be cut by a page break
  moves to the next page together with its heading and notes. A table longer
  than a page still runs over, with its column headings repeated on every page.
- **Chapters and tables** — a tree of the report's chapters and the tables in
  each (one per subsection: each case's displacements, reactions, storey table,
  each design check…). Uncheck what should stay out; unchecking a chapter takes
  its subsections with it. **Select All** and **Select None** set the whole
  tree. The tree lists what this report has, so a check added to the program
  appears in it on its own.

# Contents
- **Project** — name, description, author, date, units, model type and program
  version.
- **Model** — joints, supports, elements by type, materials, sections, patterns,
  cases, combinations, storeys, groups and section cuts, counted.
- **Materials** and **Sections** — every one with its values.
- **Load patterns** — the loads each holds and the sum of its joint loads.
- **Analysis cases** and **Load combinations** — with their patterns and terms.
- **Results** — one section per case run in this session *on the model as it is
  now*: peak displacements (and where), support reactions with their sum, the
  pushover curve, the periods, the storey table and the section cuts. Values
  are in the display units, with the Results panel's signs.
- **Steel frame check** — when the project has design settings (saved by
  Design → Steel Frame Check): the method, Fy, Fu, ratio limit and load sets, every
  checked member with its governing ratio, check, equation and load set, and the
  amplified storey drifts against the limit. Its values are in the project's units.
- **Seismic and connection checks** — when the project has them: the SMF joint
  table (E3.4a, panel zone J10.6 and continuity plates E3.6f), the AISC 358-22
  RBS connections and 5.5 web checks, the SCBF protected zones, gussets and
  F2.6c brace connections, the F2.6b joints, the F2.6d column splices, the
  F2.3 capacity design and the AISC 360 Chapter J checks, with their notes.

# Notes
- Results computed before the last model change are left out; run the cases again
  first. Nothing is run by the report itself.
- Long tables stop at 60 rows; the Results panel exports any table in full (CSV).
- Values below a billionth of a table's largest one print as 0 (solver
  round-off).
