"""Contextual help: what every command is for, what its parameters mean, and
the mechanics behind the analysis it starts.

F1 anywhere opens the help at whatever the user is looking at. The pages are
data, one file per topic in ``data/help/<topic id>.md``, grouped the way the
menu bar is; the window that shows them is
:mod:`opensees_studio.views.help_window`, and the mapping from a menu action to
its topic is :data:`ACTION_TOPICS` (keyed by the action's attribute name on the
main window, so a new action without help fails a test rather than opening
nothing). The OpenSees command glossary (:mod:`core.help_glossary`) is built
from its own tables.

A page starts with a front matter between two ``---`` lines::

    ---
    title: Define → Storeys
    group: Define
    summary: One line under the title.
    see_also: assign.diaphragm, mechanics.buildings
    order: 2130
    ---

``group`` is one of :data:`GROUP_ORDER`; ``order`` places the page among the
others of its group (gaps of ten leave room for a new one); ``summary`` and
``see_also`` may be left out. The body below is prose in a tiny markup instead
of HTML: paragraphs separated by blank lines, ``-`` for bullets, ``#`` for a
heading, and ``**bold**``. :func:`body_to_html` turns that into what
``QTextBrowser`` renders.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path

from opensees_studio.core.help_glossary import GLOSSARY_GROUP, glossary_pages

#: Topic shown when nothing more specific is known.
DEFAULT_TOPIC = "index"

#: Qt property an action or a dialog carries to name its help topic.
TOPIC_PROPERTY = "helpTopic"

#: Where the pages live, one ``<topic id>.md`` each.
HELP_DIR = Path(__file__).resolve().parents[1] / "data" / "help"

#: Where the glossary pages sit among the ``order`` values of the pages.
GLOSSARY_ORDER = 2020


@dataclass(frozen=True)
class HelpTopic:
    """One page of help."""

    title: str
    group: str
    summary: str = ""
    body: str = ""
    see_also: tuple[str, ...] = field(default=())

    def html(self, *, resolver: object | None = None) -> str:
        """The topic as HTML, with its cross-references as links."""
        parts = [f"<h2>{html.escape(self.title)}</h2>"]
        if self.summary:
            parts.append(f"<p><i>{html.escape(self.summary)}</i></p>")
        parts.append(body_to_html(self.body))
        if self.see_also:
            links = []
            for topic_id in self.see_also:
                target = TOPICS.get(topic_id)
                label = html.escape(target.title if target else topic_id)
                links.append(f'<a href="topic:{topic_id}">{label}</a>')
            parts.append("<h4>See also</h4><p>" + " · ".join(links) + "</p>")
        del resolver
        return "".join(parts)


#: Groups in the order they appear in the help window's contents tree.
GROUP_ORDER: tuple[str, ...] = (
    "Getting started",
    "File",
    "Edit and tools",
    "Define",
    "Assign — joints",
    "Assign — frame",
    "Assign — areas",
    "Assign — groups",
    "Analyze",
    "Display",
    "Design",
    "View",
    "Options",
    "Help",
    "Mechanics",
    "Annex — OpenSees commands",
)


def body_to_html(text: str) -> str:
    """The tiny markup used above, as HTML for a ``QTextBrowser``.

    Blank line separates paragraphs, ``- `` starts a bullet, ``# `` a heading,
    and ``**bold**`` is bold. Everything else is escaped text.
    """
    out: list[str] = []
    bullets: list[str] = []

    def flush_bullets() -> None:
        if bullets:
            out.append("<ul>" + "".join(f"<li>{item}</li>" for item in bullets) + "</ul>")
            bullets.clear()

    for block in text.strip().split("\n"):
        line = block.strip()
        if not line:
            flush_bullets()
            continue
        if line.startswith("- "):
            bullets.append(_inline(line[2:]))
            continue
        flush_bullets()
        if line.startswith("# "):
            out.append(f"<h3>{_inline(line[2:])}</h3>")
        else:
            out.append(f"<p>{_inline(line)}</p>")
    flush_bullets()
    return "".join(out)


def _inline(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)


def resolve_topic(
    *,
    highlighted: str | None = None,
    menu_first: str | None = None,
    widget_topics: tuple[str | None, ...] = (),
) -> str:
    """Which page F1 should show, from what the caller found on screen.

    In order: the item under the cursor in the open menu, the first entry of
    that menu (a menu is open but nothing is highlighted), then whatever dialog
    or window is on top. Unknown ids are ignored rather than shown blank.
    """
    for candidate in (highlighted, menu_first, *widget_topics):
        if candidate and candidate in TOPICS:
            return candidate
    return DEFAULT_TOPIC


def topic(topic_id: str) -> HelpTopic:
    """The topic, or the default one when the id is unknown."""
    return TOPICS.get(topic_id) or TOPICS[DEFAULT_TOPIC]


def topics_in_group(group: str) -> list[tuple[str, HelpTopic]]:
    """Every topic of a group, in the order they were written."""
    return [(key, value) for key, value in TOPICS.items() if value.group == group]


def groups_present() -> list[str]:
    """The groups that actually have topics, in display order."""
    present = {value.group for value in TOPICS.values()}
    return [group for group in GROUP_ORDER if group in present]


def parse_page(text: str, topic_id: str = "") -> tuple[HelpTopic, int]:
    """A page file's topic and its ``order``.

    Raises:
        ValueError: when the front matter is missing, a key is unknown, or the
            title, group or order is not there.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"help page {topic_id!r}: no front matter")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise ValueError(f"help page {topic_id!r}: the front matter is not closed") from None
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep or key.strip() not in {"title", "group", "summary", "see_also", "order"}:
            raise ValueError(f"help page {topic_id!r}: unknown front matter line {line!r}")
        fields[key.strip()] = value.strip()
    for required in ("title", "group", "order"):
        if not fields.get(required):
            raise ValueError(f"help page {topic_id!r}: no {required}")
    see_also = tuple(s.strip() for s in fields.get("see_also", "").split(",") if s.strip())
    body = "\n".join(lines[end + 1 :]).strip("\n")
    page = HelpTopic(
        title=fields["title"],
        group=fields["group"],
        summary=fields.get("summary", ""),
        body=body,
        see_also=see_also,
    )
    return page, int(fields["order"])


def load_topics(folder: Path = HELP_DIR) -> dict[str, HelpTopic]:
    """Every page of ``folder`` and the glossary, in the order the pages give."""
    placed: list[tuple[int, int, str, HelpTopic]] = []
    for path in folder.glob("*.md"):
        page, order = parse_page(path.read_text(encoding="utf-8"), path.stem)
        placed.append((order, 0, path.stem, page))
    for rank, (page_id, title, summary, body, see_also) in enumerate(glossary_pages()):
        page = HelpTopic(
            title=title, group=GLOSSARY_GROUP, summary=summary, body=body, see_also=see_also
        )
        placed.append((GLOSSARY_ORDER, rank, page_id, page))
    placed.sort(key=lambda item: (item[0], item[1], item[2]))
    return {page_id: page for _order, _rank, page_id, page in placed}


#: Every page by its id.
TOPICS: dict[str, HelpTopic] = load_topics()


#: Menu action (attribute name on the main window) → topic.
ACTION_TOPICS: dict[str, str] = {
    # ── File ────────────────────────────────────────────────────────
    "_act_new_model": "file.new_model",
    "_act_new": "file.new",
    "_act_new_2d": "file.new_2d_frame",
    "_act_new_2d_truss": "file.new_2d_truss",
    "_act_open": "file.open",
    "_act_save": "file.save",
    "_act_save_as": "file.save_as",
    "_act_import_dxf": "file.import_dxf",
    "_act_import_s3d": "file.import_s3d",
    "_act_import_s2k": "file.import_s2k",
    "_act_import_tcl": "file.import_tcl",
    "_act_design_basis": "design.basis",
    "_act_direct_analysis": "design.direct_analysis",
    "_act_member_classification": "design.member_classification",
    "_act_steel_check": "design.steel_check",
    "_act_dark_mode": "options.dark_mode",
    "_act_use_ribbon": "options.ribbon",
    "_act_concrete_check": "design.concrete_check",
    "_act_footings": "design.footings",
    "_act_footing_pressures": "design.footing_pressures",
    "_act_vis_footings": "view.visibility",
    "_act_base_plates": "design.base_plates",
    "_act_joint_connections": "design.joint_connections",
    "_act_built_up": "design.built_up",
    "_act_base_plate": "design.base_plate",
    "_act_bolted": "design.bolted_connection",
    "_act_connections": "design.connections",
    "_act_gussets": "design.gussets",
    "_act_column_splices": "design.column_splices",
    "_act_chapter_j": "design.chapter_j",
    "_act_notional_loads": "design.notional_loads",
    "_act_influence_line": "display.influence_line",
    "_act_drift_check": "design.drift_check",
    "_act_steel_ratios": "design.steel_ratios",
    "_act_export_script": "file.export_script",
    "_act_export_ifc": "file.export_ifc",
    "_act_import_ifc": "file.import_ifc",
    "_act_export_s2k": "file.export_s2k",
    "_act_export_report": "file.export_report",
    "_act_calc_memory": "file.calc_memory",
    "_act_project_info": "file.project_info",
    "_act_run_batch": "file.run_batch",
    "_act_quit": "file.quit",
    # ── Edit and tools ──────────────────────────────────────────────
    "_act_undo": "edit.undo",
    "_act_redo": "edit.redo",
    "_act_delete": "edit.delete",
    "_act_clear_selection": "edit.clear_selection",
    "_act_select_all": "edit.select_all",
    "_act_table_editing": "edit.table_editing",
    "_act_invert_selection": "select.menu",
    "_act_previous_selection": "select.menu",
    "_act_select_line": "select.menu",
    "_act_select_all_joints": "select.menu",
    "_act_select_all_elements": "select.menu",
    "_act_select_supports": "select.menu",
    "_act_select_joints_with_mass": "select.menu",
    "_act_select_joints_of_elements": "select.menu",
    "_act_select_elements_within_joints": "select.menu",
    "_act_select_weighted": "select.menu",
    "_act_move": "edit.move",
    "_act_replicate": "edit.replicate",
    "_act_copy": "edit.copy_paste",
    "_act_paste": "edit.copy_paste",
    "_act_check_duplicates": "edit.check_duplicates",
    "_act_mesh": "edit.mesh",
    "_act_merge_joints": "edit.merge_joints",
    "_act_divide_frames": "edit.divide_frames",
    "_act_select_loose_joints": "select.menu",
    "_act_select_joints_in_bars": "select.menu",
    "_act_select_shell_edge_joints": "select.menu",
    "_act_mirror": "edit.mirror",
    "_act_join_frames": "edit.join_frames",
    "_act_extrude": "edit.extrude",
    "_act_tool_select": "tools.select",
    "_act_tool_draw_node": "tools.draw_node",
    "_act_tool_draw_frame": "tools.draw_frame",
    "_act_tool_draw_truss": "tools.draw_truss",
    "_act_tool_quick_frame": "tools.quick_frame",
    "_act_tool_quick_shell": "tools.quick_frame",
    "_act_tool_measure": "tools.measure_distance",
    "_act_tool_draw_shell": "tools.draw_shell",
    # ── Define ──────────────────────────────────────────────────────
    "_act_grid": "define.grid",
    "_act_grid_wizard": "define.grid_wizard",
    "_act_show_grids": "view.grids",
    "_act_show_grid_labels": "view.grids",
    "_act_grid_line_view": "view.grid_line_view",
    "_act_show_all_objects": "view.visibility",
    "_act_add_node": "define.add_node",
    "_act_storeys": "define.storeys",
    "_act_groups": "define.groups",
    "_act_joint_patterns": "define.joint_patterns",
    "_act_section_cuts": "define.section_cuts",
    "_act_assign_group": "assign.group",
    "_act_mass_source": "define.mass_source",
    "_act_seismic_loads": "define.seismic_loads",
    "_act_create_shell": "define.create_shell",
    "_act_shell_formulation": "assign.shell_formulation",
    "_act_frame_wizard": "define.portal_frame",
    "_act_truss_wizard": "define.truss",
    "_act_warehouse_wizard": "define.warehouse",
    "_act_building_wizard": "define.building",
    "_act_material_library": "define.material_library",
    "_act_default_materials": "define.default_materials",
    "_act_friction_library": "define.friction_library",
    "_act_material_tester": "define.material_tester",
    "_act_ground_motions": "define.ground_motions",
    "_act_section_library": "define.section_library",
    "_act_concrete_section": "define.concrete_section",
    "_act_steel_deck": "define.steel_deck",
    "_act_section_designer": "define.section_designer",
    "_act_add_linear_ts": "define.linear_ts",
    "_act_add_path_ts": "define.path_ts",
    "_act_add_function_ts": "define.function_ts",
    "_act_constant_ts": "define.constant_ts",
    "_act_add_multi_support": "define.multi_support",
    "_act_custom_commands": "define.custom_commands",
    "_act_assign_link": "assign.link",
    "_act_add_plain_pattern": "define.plain_pattern",
    "_act_add_uniform_excitation": "define.uniform_excitation",
    "_act_load_combinations": "define.load_combinations",
    # ── Assign: joints ──────────────────────────────────────────────
    "_act_assign_support": "assign.support",
    "_act_restraint_fixed": "assign.support",
    "_act_restraint_pinned": "assign.support",
    "_act_restraint_roller": "assign.support",
    "_act_restraint_free": "assign.support",
    "_act_assign_masses": "assign.masses",
    "_act_assign_springs": "assign.springs",
    "_act_assign_equal_dof": "assign.equal_dof",
    "_act_assign_diaphragm": "assign.diaphragm",
    "_act_assign_rigid_link": "assign.rigid_link",
    "_act_remove_constraints": "assign.remove_constraints",
    "_act_assign_load": "assign.load",
    "_act_assign_imposed_displacement": "assign.imposed_displacement",
    "_act_assign_joint_pattern": "assign.joint_pattern",
    "_act_assign_surface_load": "assign.surface_load",
    "_act_assign_area_springs": "assign.area_springs",
    "_act_assign_edge_springs": "assign.edge_springs",
    "_act_assign_line_springs": "assign.line_springs",
    "_act_assign_floor_load": "assign.floor_load",
    "_act_assign_zero_length": "assign.zero_length",
    "_act_assign_zls": "assign.zero_length_section",
    "_act_assign_bearing": "assign.bearing",
    # ── Assign: frame ───────────────────────────────────────────────
    "_act_assign_section": "assign.section",
    "_act_assign_material": "assign.material",
    "_act_assign_geom_transf": "assign.geom_transf",
    "_act_assign_local_axes": "assign.local_axes",
    "_act_assign_integration": "assign.integration",
    "_act_assign_distributed_load": "assign.distributed_load",
    "_act_assign_frame_point_load": "assign.frame_point_load",
    "_act_assign_releases": "assign.frame_releases",
    "_act_assign_end_offsets": "assign.end_offsets",
    "_act_assign_insertion": "assign.insertion_point",
    "_act_assign_modifiers": "assign.property_modifiers",
    "_act_assign_trapezoidal_load": "assign.trapezoidal_load",
    "_act_assign_temperature_load": "assign.temperature_load",
    "_act_assign_hinge": "assign.hinge",
    "_act_assign_wall": "assign.wall",
    "_act_assign_tendon": "assign.tendon",
    "_act_assign_pile": "assign.pile_springs",
    "_act_mc2010": "define.mc2010",
    # ── Analyze ─────────────────────────────────────────────────────
    "_act_case_manager": "analyze.cases",
    "_act_check_model": "analyze.check_model",
    "_act_run": "analyze.run",
    "_act_run_all": "analyze.run_all",
    "_act_run_selected": "analyze.run_selected",
    "_act_clear_results": "analyze.clear_results",
    "_act_auto_mesh_frames": "analyze.auto_mesh",
    "_act_assign_auto_mesh": "analyze.auto_mesh",
    "_act_tension_only": "assign.tension_only",
    "_act_check_stability": "analyze.stability",
    "_act_cancel_stability": "analyze.stability",
    # ── Display ─────────────────────────────────────────────────────
    "_act_select_results": "display.select_results",
    "_act_show_deformed": "display.deformed",
    "_act_show_mode_shape": "display.mode_shape",
    "_act_show_force_diagram": "display.force_diagram",
    "_act_show_reactions": "display.reactions",
    "_act_reactions_table": "display.reactions_table",
    "_act_reactions_dialog": "display.reactions_dialog",
    "_act_shell_contours": "display.shell_contours",
    "_act_show_time_history": "display.time_history",
    "_act_export_th_animation": "display.export_animation",
    "_act_show_hysteresis": "display.hysteresis",
    "_act_show_pushover": "display.pushover",
    "_act_show_response_spectrum": "display.response_spectrum",
    "_act_display_options": "display.options",
    "_act_show_load_assigns": "display.load_assigns",
    "_act_back_to_model": "display.back_to_model",
    # ── View ────────────────────────────────────────────────────────
    "_act_zoom_extents": "view.zoom_extents",
    "_act_view_iso": "view.iso",
    "_act_view_top": "view.top",
    "_act_view_front": "view.front",
    "_act_view_right": "view.right",
    "_act_level_up": "view.move_in_list",
    "_act_level_down": "view.move_in_list",
    "_act_toggle_parallel": "view.parallel",
    "_act_show_extruded": "view.show_extruded",
    "_act_zoom_in": "view.zoom_extents",
    "_act_zoom_out": "view.zoom_extents",
    "_act_zoom_window": "view.zoom_extents",
    "_act_hide_selected": "view.visibility",
    "_act_isolate_selected": "view.visibility",
    "_act_invert_visible": "view.visibility",
    "_act_view_colors": "view.colors",
    "_act_new_view": "view.new_window",
    "_act_close_view": "view.close_window",
    "_act_reset_layout": "view.panels",
    "_act_vis_grids": "view.visibility",
    "_act_vis_grid_labels": "view.visibility",
    "_act_vis_nodes": "view.visibility",
    "_act_vis_frames": "view.visibility",
    "_act_vis_surfaces": "view.visibility",
    "_act_vis_supports": "view.visibility",
    "_act_vis_constraints": "view.visibility",
    "_act_vis_frame_assignments": "view.visibility",
    "_act_vis_releases": "view.visibility",
    "_act_vis_loads": "view.visibility",
    "_act_vis_node_labels": "view.visibility",
    "_act_vis_element_labels": "view.visibility",
    "_act_vis_extruded": "view.show_extruded",
    "_act_show_local_axes": "view.local_axes",
    # ── Options and Help ────────────────────────────────────────────
    "_act_set_units": "options.units",
    "_act_solver_settings": "options.solver",
    "_act_lock_model": "options.lock_model",
    "_act_delete_loads": "edit.delete_loads",
    "_act_color_none": "view.color_by",
    "_act_color_section": "view.color_by",
    "_act_color_material": "view.color_by",
    "_act_color_group": "view.color_by",
    "_act_rotate_left": "view.rotate",
    "_act_rotate_right": "view.rotate",
    "_act_rotate_up": "view.rotate",
    "_act_rotate_down": "view.rotate",
    "_act_spin": "view.rotate",
    "_act_help_contents": "help.contents",
    "_act_shortcuts": "help.shortcuts",
    "_act_about": "help.about",
    "_act_performance": "help.performance",
}
