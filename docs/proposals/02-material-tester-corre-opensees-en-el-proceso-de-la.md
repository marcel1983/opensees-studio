# 02. Material Tester corre OpenSees en el proceso de la GUI (crash 0xC000041D)

- **Tipo:** Corregir
- **Etiquetas:** bug, roadmap
- **Estado:** propuesta

## Problema
`viewmodels/material_tester_vm.py` llama `test_uniaxial_material` directamente en el proceso de la GUI: una entrada no soportada que haga que OpenSees termine el proceso tumba la aplicación. Se vio `0xC000041D` una vez en 26 corridas de `tests/gui/test_material_tester_dialog.py` (2026-09-22).

## Propuesta
Mover la ejecución a la ruta CLI (modo `--material-test` o segundo entry point con el mismo protocolo JSON que el runner), o validar las entradas antes de emitirlas.

## Criterios de aceptación
- [ ] Un material que haga hard-exit no cierra la GUI; se muestra un error
- [ ] Capturar la salida completa de faulthandler si reaparece

---
Fuente: `docs/roadmap.md`. Al cerrar, marcar el ítem como ✅ en el roadmap y añadir la entrada al `CHANGELOG.md`.
