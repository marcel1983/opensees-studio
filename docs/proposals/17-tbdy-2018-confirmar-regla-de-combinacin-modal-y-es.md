# 17. TBDY 2018: confirmar regla de combinación modal y espectro reducido Ra / SaR

- **Tipo:** Desarrollar
- **Etiquetas:** enhancement, roadmap
- **Estado:** propuesta

Requiere confirmación del ingeniero:
- [ ] Regla de combinación modal: CQC entre modos; amortiguamiento de 5 %; umbral de modos cercanos 0.9
- [ ] Espectro reducido: Ra(T) = D + (R/I − D)·T/TB si T < TB, R/I si T ≥ TB; SaR = Sae/Ra, con R, D e I ingresados por el usuario

Opcional: consulta de la grilla AFAD (Ss, S1, PGA, PGV por latitud y longitud) como extra opcional; requiere scipy y un JSON de 2.2 MB.

---
Fuente: `docs/roadmap.md`. Al cerrar, marcar el ítem como ✅ en el roadmap y añadir la entrada al `CHANGELOG.md`.
