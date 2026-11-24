---
title: Menu map: where each command is
group: Getting started
summary: Every menu and what its entries do, in one page.
see_also: index, annex.index
order: 20
---

# File
- New Model (units and a template), New (blank 3D model, 2D frame, 2D truss),
  Open, Open Recent, Save, Save As, Quit.
- Import → DXF drawing, PORTICO model (.s3d), SAP2000 text (.s2k / .$2k). Export →
  OpenSees script (.py), IFC (.ifc), SAP2000 text (.s2k), Report (PDF or HTML).

# Edit
- Undo / Redo, Delete, Select All, Clear Selection.
- Move, Replicate, Mirror; Interactive Table Editing (Ctrl+T); Check Model for
Duplicates; Mesh.

# Select
- Invert, Previous; All Joints / Elements; By Element Type, Section, Material,
Load Pattern or Group; Supported Joints, Joints with Mass, Elements with Self
Weight; Joints of Selected Elements, Elements between Selected Joints.

# Draw
- Select, Draw Node, Draw Frame, Draw Truss.
- Object snaps on members (midpoint, perpendicular, nearest point) from the
  left-hand icon bar.

# Define
- Geometry and building: Coordinate System/Grids, Grid Wizard, Add Node, Storeys, Groups,
Section Cuts, Mass Source, Seismic Loads (ELF), Create Shell from 3 or 4 Nodes,
Create Portal Frame, Create Truss.
- Properties: Material Library (40 materials, Material Tester to check one),
Friction Models, Ground Motions, Section Library (elastic, nonprismatic, fibre
with W and RC templates, aggregator, plate, LayeredShell, PlateFiber, AISC
shapes).
- Loads: Add Linear / Path / Function / Constant TimeSeries, Add Plain Load Pattern, Add
Uniform Excitation, Add Multi-Support Excitation, Load Combinations.
- Custom OpenSees Commands: Python blocks for anything without a form.

# Assign
- Joint: Restraints, Masses, Springs, EqualDOF, Diaphragm, Rigid Link, Remove
Constraints, Point Loads, Imposed Displacement, Zero-Length Element and
Section, Bearing, Link (twoNodeLink, Triple Friction Pendulum).
- Frame: Section, Material, Geometric Transformation, Beam Integration,
Releases/Partial Fixity, End Offsets, Insertion Point, Property Modifiers,
Distributed, Trapezoidal and Point Loads, Plastic Hinge.
- Area: Surface Load on Shells, Floor Load to Frames.
- Assign to Group (Ctrl+Shift+G).

# Analyze
- Cases (static, modal, pushover, transient, response spectrum, with every solver
option OpenSees 3.8 runs), Check Model Stability, Run.

# Display
- Show Results Of, Deformed Shape, Animate Mode Shape, Force Diagram, Shell
Contours, Time-History Plot and Animation, Hysteresis, Pushover Curve, Response
Spectrum, Display Options, Back to Model View. The Results panel holds the
tables (storeys, section cuts) and exports them to CSV.

# Design
In the order a steel design is done:
- Design Basis (AISC), Direct Analysis Method, Generate Notional Loads (DAM);
- Member Classification, Built-Up Shapes;
- Steel Frame Check (AISC 360-16), Display Steel Ratios on Model, Storey Drift
  Check;
- **Steel Connections**: Connections by Joint, Base Plates (Column Bases),
  Connections (AISC 358-22), Gussets (AISC 341-22), Column Splices (AISC
  341-22), Connection Checks (AISC 360 J);
- **Connection Calculators** for one connection at a time: Base Plate & Anchors
  (DG1, ACI 318), Bolted Connection (Prying, Bolt Group);
- Concrete Frame Check (ACI 318-19).

# View, Options, Help
- Zoom Extents, Isometric / Top / Front / Right, Parallel Projection, Extruded
Sections, Show Grids, Show Grid Labels, Grid Line View, Hide Selected, Isolate
Selected, Show All Objects; Set Display Units; Help Contents (F1), Keyboard
Shortcuts, About.
- **Right-click** on the model view (without dragging: a right drag zooms): with
something selected, what can be assigned or edited on it (joint, frame or area
options, group, move, replicate, mirror, delete); with nothing selected, the
grid and view options.
