---
title: Options → Use Ribbon
group: Options
summary: The ribbon: the menu commands in the order a model is built.
see_also: design.steel_check, design.connections
order: 1890
---

The ribbon is a **second way to reach the same commands**, not a different
program. Every button is the menu action it replaces: same shortcut, same
enabled state, same dialog, same help page.

# The tabs, left to right

``Home · Define · Draw · Select · Assign · Loads · Analyze · Results · Design · View · Help``

- **Home** - new model, open, save, undo, import and export, session options.
- **Define** - grids and storeys, materials, sections, load patterns and time
  series, cases and combinations.
- **Draw** - the drawing tools, the wizards and the geometry edits (move,
  replicate, mirror, extrude, divide, join, mesh).
- **Select** - select all, clear, invert, previous, intersecting line, and by
  type, section, material, pattern or group.
- **Assign** - restraints, springs, constraints, joint elements, frame sections
  and releases, nonlinear hinges and walls, shell formulation.
- **Loads** - joint, frame and area loads, and the review of the load assigns.
- **Analyze** - check model, stability, run.
- **Results** - deformed shape, mode shapes, force diagrams, reactions,
  time-history, pushover and spectrum plots.
- **Design** - the steel design basis and checks, connections, concrete check.
- **View** - zoom, standard views, rotation, visibility and colours, windows.

Each group shows its main command as a **large button** and the others as small
ones, all with their label. A submenu (Import, Export, Open Recent, Time Series,
Color By, Language…) is one drop-down button. Every menu command has exactly one
place in the ribbon.

# Icons

Every command has its own icon, the same in the ribbon, the menus and the
toolbars: what it acts on (a joint, a member, a shell, a load) with a blue badge
for what it does (add, check, import, export, show). The icons are SVG files in
`opensees_studio/data/icons`, named after the command, and can be edited in any
SVG editor.

# The dock

On the right, **Proyecto** carries three panels:

- **Árbol** - every entity by category, with counts; click locates it and a
  double click selects it for editing.
- **Editar** - the categories and the rows of the chosen one; the buttons open
  the existing editors (table editing, delete).
- **Ayuda** - the page of the current tab.

# Menus or ribbon

Turn **Use Ribbon** off to work with the classic menus again; the choice is
remembered. The ribbon's **Menús** button shows the menu bar without leaving the
ribbon, for one command.
