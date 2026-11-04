# 01. rc_frame_earthquake se detiene en t ≈ 0.99 s (98 de 400 pasos)

- **Tipo:** Corregir
- **Etiquetas:** bug, tech-debt, roadmap
- **Estado:** propuesta

## Problema
El ejemplo `rc_frame_earthquake` no completa el análisis. Desde que el registro se redondeó a 6 decimales (`dd67bf7`) se detiene en el paso 99 (t = 0.99 s); antes llegaba a 192/400. La aserción de pasos en `tests/integration/test_rc_frame_earthquake.py` está como `xfail(strict=True)`.

## Diagnóstico propuesto (en este orden)
1. **Unidades y escala**: confirmar que el modelo está en kip-in (la masa se reporta en kip·s²/in); revisar que `g` no se aplique dos veces ni ninguna; verificar el factor de escala del registro. Ux del nudo 3 llega a ±1.5 unidades.
2. Solo si el modelo es físicamente correcto: sub-stepping al fallar, `KrylovNewton`, test `EnergyIncr`/`NormUnbalance`, y comparación contra OpenSees Ex3.3.

## Criterios de aceptación
- [ ] Causa identificada y documentada
- [ ] 400/400 pasos; quitar el `xfail`
- [ ] Endurecer la aserción de deriva (`|Ux| < 14.4` es demasiado laxa)

---
Fuente: `docs/roadmap.md`. Al cerrar, marcar el ítem como ✅ en el roadmap y añadir la entrada al `CHANGELOG.md`.
