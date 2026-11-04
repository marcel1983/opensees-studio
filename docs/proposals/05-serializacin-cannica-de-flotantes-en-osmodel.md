# 05. Serialización canónica de flotantes en .osmodel

- **Tipo:** Corregir
- **Etiquetas:** tech-debt, roadmap
- **Estado:** propuesta

Regenerar los ejemplos en Linux cambió solo el último dígito de algunos flotantes en 18 `.osmodel` no-GM (ruido de plataforma) y los movería de schema 1 a 2. Por eso esos 18 siguen en schema 1.

## Propuesta
Serializar flotantes de forma canónica (p. ej. `repr` de Python / shortest round-trip, o redondeo a N cifras significativas) para que el archivo sea idéntico byte a byte entre plataformas. Luego regenerar todos los ejemplos a schema 2.

---
Fuente: `docs/roadmap.md`. Al cerrar, marcar el ítem como ✅ en el roadmap y añadir la entrada al `CHANGELOG.md`.
