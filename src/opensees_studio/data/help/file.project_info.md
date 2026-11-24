---
title: File → Project Information
group: File
summary: Project, author, company, date and revisions used by the report cover.
see_also: file.export_report
order: 520
---

The calculation report starts with a cover built from these fields:

- **Project**, **Author**, **Company** and **Date**: free text; the date starts
  as today's.
- **Description**: a short paragraph under the project name.
- **Revisions**: one row per revision (`Rev`, `Date`, `By`, `Description`).
  Empty revision codes are ignored when the project is saved.

The values are stored in `Project.meta` in the `.osmodel`, are undoable as one
step, and are used by the report and by the calculation memory.
