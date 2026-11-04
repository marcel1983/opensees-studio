# 03. Revisar tol 1e-12 en los casos de análisis de 4 ejemplos

- **Tipo:** Corregir
- **Etiquetas:** tech-debt, roadmap
- **Estado:** propuesta

Los casos de análisis de `beam_quad_2d`, `ex1a_canti2d_eq`, `rc_frame_gravity` y `rc_frame_pushover` (scripts y `.osmodel`) usan tolerancia 1e-12, que es demasiado estricta para el test global y puede ocultar o provocar problemas de convergencia.

No tocar el 1e-12 / 10 interno de `ForceBeamColumn`, que es el valor por defecto de OpenSees.

- [ ] Ajustar a una tolerancia razonable (p. ej. 1e-8) y regenerar
- [ ] Resultados sin cambios dentro de la tolerancia de los tests

---
Fuente: `docs/roadmap.md`. Al cerrar, marcar el ítem como ✅ en el roadmap y añadir la entrada al `CHANGELOG.md`.
