"""The fields of the Earthquake page of the Warehouse Wizard that differ per direction.

Across the frames (X) a warehouse holds by its portal frames and along the
building (Y) by its wall bracing, so each direction has its own reduction
factor and, with the period, its own system and period.
:meth:`SeismicDirectionFields.seismic_fields` hands them to
:class:`~opensees_studio.core.warehouse.WarehouseSeismic`.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QComboBox, QFormLayout

from opensees_studio.core.seismic_codes.asce7_16 import ASCE_PERIOD_SYSTEMS
from opensees_studio.core.warehouse import PERIOD_METHODS
from opensees_studio.views.dialogs.frame_wizard import _field
from opensees_studio.views.i18n import tr

_PERIOD_TIP = (
    "The fundamental period in this direction, for example from a modal case. 0 takes "
    "the empirical period of the system at the mean roof height: Ta = Ct hn^x of "
    "ASCE 7-16 Eq. 12.8-7 (NSCM too) or T1 = Ct H^(3/4) of EN 1998-1 (4.6). RNC-07 has "
    "no empirical period: type it (Art. 32 b)."
)


class SeismicDirectionFields(QObject):
    """Reduction factor along Y, period method, periods and systems; ``changed`` on any edit."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.reduction_y = _field(0.0, minimum=0.0, maximum=20.0, step=0.5)
        self.reduction_y.setSpecialValueText(tr("Same as along X"))
        self.reduction_y.setToolTip(
            "The reduction factor of the lateral system along the building, usually the "
            "wall bracing (a concentric braced frame), when it differs from that of the "
            "portal frames across. 0 takes the same as along X."
        )
        self.period_method = QComboBox()
        for key, label in PERIOD_METHODS.items():
            self.period_method.addItem(tr(label), userData=key)
        self.period_method.setToolTip(
            "The plateau of the design spectrum needs no period and is on the safe side. "
            "With the period, the coefficient of each direction is read from the design "
            "spectrum at the period of that direction."
        )
        self.period_x = _field(0.0, minimum=0.0, maximum=100.0, step=0.05, suffix="s")
        self.period_y = _field(0.0, minimum=0.0, maximum=100.0, step=0.05, suffix="s")
        self.system_x = QComboBox()
        self.system_y = QComboBox()
        for box, field, default in (
            (self.system_x, self.period_x, "steel_mrf"),
            (self.system_y, self.period_y, "other"),
        ):
            for key, (label, _ct, _x) in ASCE_PERIOD_SYSTEMS.items():
                box.addItem(tr(label), userData=key)
            box.setCurrentIndex(box.findData(default))
            box.setToolTip(
                "The lateral system of this direction, for the empirical period: a steel "
                "moment frame across the portal frames, a braced frame (all other systems) "
                "along the building."
            )
            box.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            box.setMinimumContentsLength(24)
            field.setSpecialValueText(tr("Empirical"))
            field.setToolTip(_PERIOD_TIP)
            box.currentIndexChanged.connect(self.changed)
            field.valueChanged.connect(self.changed)
        self.sd1 = _field(0.6, minimum=0.0, maximum=10.0, step=0.1, suffix="g")
        self.sd1.setToolTip(
            "ASCE 7-16 11.4.5: design spectral acceleration at 1 s, SD1. It caps the "
            "coefficient beyond the plateau and sets Cu of Table 12.8-1."
        )
        self.reduction_y.valueChanged.connect(self.changed)
        self.period_method.currentIndexChanged.connect(self.changed)
        self.sd1.valueChanged.connect(self.changed)

    def add_to(self, form: QFormLayout) -> None:
        """Rows for ``form``, after the reduction factor along X."""
        form.addRow("Reduction factor along Y:", self.reduction_y)
        form.addRow("Seismic coefficient from:", self.period_method)
        form.addRow("System along X:", self.system_x)
        form.addRow("Period along X:", self.period_x)
        form.addRow("System along Y:", self.system_y)
        form.addRow("Period along Y:", self.period_y)
        form.addRow("SD1:", self.sd1)

    def refresh(self, on: bool, method: str, directions: set[str]) -> None:
        """Enable what ``method`` uses, for the ``directions`` asked for."""
        with_period = self.period_method.currentData() == "period"
        empirical = method != "rnc07"
        self.reduction_y.setEnabled(on and "Y" in directions)
        self.period_method.setEnabled(on)
        for direction, system, period in (
            ("X", self.system_x, self.period_x),
            ("Y", self.system_y, self.period_y),
        ):
            used = on and with_period and direction in directions
            system.setEnabled(used and empirical)
            period.setEnabled(used)
            period.setSpecialValueText(tr("Empirical") if empirical else "")
        self.sd1.setEnabled(on and with_period and method == "asce7")

    def seismic_fields(self) -> dict[str, Any]:
        """The keyword arguments of ``WarehouseSeismic`` these fields set."""
        return {
            "reduction_y": self.reduction_y.value(),
            "period_method": str(self.period_method.currentData()),
            "period_x": self.period_x.value(),
            "period_y": self.period_y.value(),
            "system_x": str(self.system_x.currentData()),
            "system_y": str(self.system_y.currentData()),
            "sd1": self.sd1.value(),
        }


__all__ = ["SeismicDirectionFields"]
