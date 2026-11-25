"""The steel design fields of the Loads page of the Warehouse Wizard.

The direct analysis method of AISC 360-16 Chapter C (every combination solved
to second order, with the reduced stiffness and the notional loads) and the
AISC 341 lateral system of each direction, which the steel check reads.
:meth:`DesignFields.loads_fields` hands them to
:class:`~opensees_studio.core.warehouse.WarehouseLoads`.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout

from opensees_studio.core.design.settings import SEISMIC_SYSTEM_LABELS
from opensees_studio.views.i18n import tr


class DesignFields(QObject):
    """Direct analysis and the AISC 341 systems; ``changed`` when any of them does."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.direct = QCheckBox("Direct analysis method (AISC 360 Chapter C)")
        self.direct.setToolTip(
            "Every combination is solved to second order under its factored loads (P-Delta, "
            "Newton), with the stiffness times 0.8 and the notional loads of C2.2b: 0.002 Yi "
            "in each direction of the gravity-only combinations, and 0.001 Yi in every one "
            "for τb = 1. The steel check then takes K = 1. LRFD codes only."
        )
        self.system_x = QComboBox()
        self.system_y = QComboBox()
        self.system_y.addItem(tr("Same as across"), userData="")
        for box in (self.system_x, self.system_y):
            for key, label in SEISMIC_SYSTEM_LABELS.items():
                box.addItem(tr(label), userData=key)
            box.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            box.setMinimumContentsLength(28)
            box.currentIndexChanged.connect(self.changed)
        self.system_x.setToolTip(
            "The AISC 341 system of the portal frames, across the building: the steel check "
            "adds its width-to-thickness and capacity design checks. None leaves the AISC "
            "360 check alone."
        )
        self.system_y.setToolTip(
            "The AISC 341 system along the building, usually the wall bracing (an ordinary "
            "or special concentrically braced frame)."
        )
        self.direct.toggled.connect(self.changed)

    def add_to(self, form: QFormLayout) -> None:
        """Rows for the Loads page."""
        form.addRow(self.direct)
        form.addRow("AISC 341 system across (X):", self.system_x)
        form.addRow("AISC 341 system along (Y):", self.system_y)

    def follow_code(self, method: str) -> None:
        """The direct analysis method is offered for LRFD codes only."""
        lrfd = method == "LRFD"
        if not lrfd:
            self.direct.setChecked(False)
        self.direct.setEnabled(lrfd)

    def loads_fields(self) -> dict[str, Any]:
        """The keyword arguments of ``WarehouseLoads`` these fields set."""
        return {
            "direct_analysis": self.direct.isEnabled() and self.direct.isChecked(),
            "seismic_system_x": str(self.system_x.currentData()),
            "seismic_system_y": str(self.system_y.currentData() or ""),
        }


__all__ = ["DesignFields"]
