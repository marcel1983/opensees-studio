# 12. Rendimiento de render: reconstrucción incremental y meta 10k nudos / 20k barras @ 30 fps

- **Tipo:** Completar
- **Etiquetas:** enhancement, performance, roadmap
- **Estado:** propuesta

Ya se hicieron varias pasadas (soportes, cargas y extrusiones en lotes; selección sin reconstrucción).

- [ ] **Reconstrucción incremental**: una edición reconstruye solo la categoría que cambió, no todas
- [ ] Recorte en GPU (menos primitivas o más ligeras)
- [ ] Medición de fotogramas reales (el benchmark actual es solo CPU)
- [ ] Mantener el ratchet de `tools/render-budget.txt`

---
Fuente: `docs/roadmap.md`. Al cerrar, marcar el ítem como ✅ en el roadmap y añadir la entrada al `CHANGELOG.md`.
