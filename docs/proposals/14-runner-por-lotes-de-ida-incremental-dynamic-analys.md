# 14. Runner por lotes de IDA (Incremental Dynamic Analysis)

- **Tipo:** Desarrollar
- **Etiquetas:** enhancement, roadmap
- **Estado:** propuesta

Corridas por lotes que escalan cada registro por niveles de intensidad (Sa(T1) o PGA) hasta el colapso o un límite de deriva.

- [ ] Algoritmo de escalado (stepping fijo y hunt & fill)
- [ ] Reutilizar `services/batch.py` y la base de resultados SQLite
- [ ] Curvas IDA y fractiles 16/50/84
- [ ] Criterio de colapso configurable (deriva o no convergencia)

---
Fuente: `docs/roadmap.md`. Al cerrar, marcar el ítem como ✅ en el roadmap y añadir la entrada al `CHANGELOG.md`.
