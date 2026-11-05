# 04. mypy: 148 errores y sin ejecución en CI

- **Tipo:** Corregir
- **Etiquetas:** tech-debt, roadmap
- **Estado:** propuesta

Hay 148 errores de mypy, 124 de ellos `union-attr` en `opensees_runner.py`. mypy no corre ni en CI ni en pre-commit.

## Propuesta
1. Corregir los `union-attr` de `opensees_runner.py` (guards/narrowing de `Optional`).
2. Añadir mypy a CI con un baseline (ratchet: el número solo baja), como ya se hace con `tools/render-budget.txt`.
3. Añadirlo a `.pre-commit-config.yaml`.

---
Fuente: `docs/roadmap.md`. Al cerrar, marcar el ítem como ✅ en el roadmap y añadir la entrada al `CHANGELOG.md`.
