# 20. README modular y mantenible

- **Tipo:** Completar (documentación)
- **Etiquetas:** documentation
- **Estado:** propuesta

## Diagnóstico del README actual

| Problema | Evidencia | Consecuencia |
|---|---|---|
| Demasiado largo | `README.md` tiene 963 líneas; «What works today» ocupa unas 350 | El lector no encuentra la instalación ni el inicio rápido; cada función nueva lo alarga más |
| Lista plana sin orden | 45 viñetas en negrita mezclan modelado, cargas, análisis, diseño, E/S y ayuda (p. ej. *Spring supports* aparece en la línea 8 y en la 70) | Duplicados y contradicciones; no está claro dónde va una función nueva |
| Manual dentro del README | Secciones completas de Material Tester, Ground motions, aisladores, marcadores de pantalla, mostrar/ocultar y chequeo de estabilidad | Duplican `core/help.py` y los tutoriales; se desactualizan por separado |
| Versiones EN/ES divergentes | `README.es.md` (242 líneas) tiene otro índice y omite secciones | Cada cambio exige dos redacciones distintas; la española ya va atrasada |
| Mezcla de audiencias | Usuario, desarrollador y mantenedor (empaquetado, perfilado) en el mismo nivel | Ninguna audiencia tiene un recorrido claro |
| Datos que caducan | Conteos («30 verified examples», «24 more uniaxial materials») y enlaces a `ogunc/...` | Cifras incorrectas tras cada PR; los enlaces de issues apuntan al upstream, y en este fork los Issues están desactivados |

## Principios

1. **El README es un índice, no un manual.** Un objetivo de unas 150 líneas: qué es, captura, por qué, instalar, primeros pasos, mapa de funciones, enlaces.
2. **Un módulo, un archivo.** Cada área funcional vive en `docs/features/<modulo>.md`, con la misma plantilla. Una función nueva toca **un** archivo de módulo y, como mucho, una fila de la tabla del README.
3. **Misma estructura en EN y ES.** `README.md` y `README.es.md` comparten encabezados y orden, sección por sección, para que se puedan revisar lado a lado. Los módulos tienen `*.es.md` como los tutoriales.
4. **Una fuente por dato.** La referencia de menús vive en `core/help.py`; la validación, en `docs/verification-manual.md`; el plan, en `docs/roadmap.md`. El README enlaza y no copia.
5. **Sin cifras que caducan** en el README; los conteos van en el módulo o se generan.

## Estructura propuesta

```
README.md / README.es.md          ← índice (~150 líneas, misma estructura)
docs/
  features/
    README.md                     ← mapa de módulos
    modeling.md                   ← ejes, retículas, nudos/barras/áreas, mallado, copiar, grupos, pisos, asistentes, tablas, vista
    materials-sections.md         ← materiales, secciones, fibra, Section Designer, AISC, muros RC, no prismáticas, Material Tester
    loads-assignments.md          ← apoyos y resortes, cargas de barra/área/temperatura, peso propio, ELF, patrones de nudo
    analysis.md                   ← tipos de caso, modal determinista, espectro, líneas de influencia, combinaciones, lotes, ajustes
    earthquake.md                 ← registros, espectros objetivo, aisladores, amortiguamiento modal
    model-checks.md               ← Check Model, estabilidad, duplicados
    results-reporting.md          ← post-proceso, base SQLite, cortes de sección, informe, animaciones
    design.md                     ← AISC 360-16 (y futuros módulos normativos)
    interoperability.md           ← DXF, SAP2000 .s2k, IFC, S3D, Tcl, exportación de scripts
  user-guide/
    install.md                    ← paquete sin Python, Options → Solver, desarrollo, headless
    display.md                    ← marcadores relativos, mostrar/ocultar/aislar
  developer/
    testing.md                    ← suites, CI, gates
    profiling.md                  ← (hoy performance-profiling.md)
```

### Plantilla de módulo (`docs/proposals/readme/feature-module-template.md`)

Cada módulo usa siempre los mismos encabezados: **Resumen** (2–3 líneas), **Funciones** (tabla: función · menú · estado ✅/🟡/⬜ · ayuda F1), **Limitaciones conocidas**, **Verificación** (casos del manual), **Ejemplos y tutoriales**, **Historial** (versión en que llegó cada función). El estado y la verificación hacen de puente con el roadmap y el manual.

## Regla de mantenimiento (para `CLAUDE.md` → «Before opening a PR»)

> Una función visible para el usuario se documenta en su módulo de `docs/features/` (EN y ES) y en `core/help.py`. El README solo cambia cuando aparece un módulo nuevo, o cambian la instalación o los primeros pasos.

Opcional: un test que compare los encabezados `##` de `README.md` y `README.es.md`, y que compruebe que cada módulo enlazado existe.

## Plan de migración (un PR por paso)

1. Crear `docs/features/` con la plantilla y mover, **sin reescribir**, las viñetas de «What works today» a su módulo (eliminando los duplicados).
2. Mover las secciones largas (Material Tester, Ground motions, aisladores, marcadores, mostrar/ocultar, estabilidad, precisión) a su módulo o a `user-guide/`.
3. Mover la instalación, las pruebas y el perfilado a `user-guide/install.md` y `developer/`.
4. Sustituir `README.md` por el índice (borrador en `docs/proposals/readme/README.draft.md`).
5. Reescribir `README.es.md` con la misma estructura y traducir los módulos.
6. Añadir la regla a `CLAUDE.md` y `CONTRIBUTING.md`, y el test de paridad.

## Criterios de aceptación

- [ ] `README.md` ≤ 200 líneas; `README.es.md` con los mismos encabezados
- [ ] Ninguna función documentada en dos sitios del README
- [ ] Cada viñeta actual de «What works today» tiene un destino en un módulo
- [ ] Enlaces verificados (incluida la decisión fork vs. `ogunc/` upstream)
