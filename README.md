# Cuaderno de Bitácora

Mapa interactivo de mis viajes (2022–2026): rutas animadas según el transporte, bitácora lateral con banderas, noches y fechas, portada con cifras, modo película a pantalla completa y un globo 3D ligero para los vuelos largos.

- **Mapa publicado**: https://claude.ai/artifact/U8xGphnYSLBCFykomoHzvL
- La documentación completa (decisiones, datos, fases y notas técnicas) está en el vault privado del proyecto.

## Compilar

```
cd codigo
npm i world-atlas@2 d3@7.8.5 topojson@3.0.2
python build.py [fotos.json]
```

Sale `mapa-de-viajes.html`, una página única con todo dentro. Sin `node_modules/world-atlas`, `build.py` usa `topo.json` y `topo110.json`.

| Archivo | Qué es |
|---|---|
| `codigo/template.html` | La página, con los marcadores `__TOPO_JSON__`, `__TOPO_LO__`, `__PHOTOS__`, `__ROUTES__`, `__HEAD__` y `__LIBS__` |
| `codigo/build.py` | Rellena los marcadores y genera la página |
| `codigo/extract_legs.js` + `codigo/build_routes.py` | Sacan los tramos de coche, bus y tren y les calculan la ruta real con Natural Earth → `routes.json` |
| `codigo/routes.json` | Rutas ya calculadas |
| `codigo/globo-*.src.html` + `codigo/extract_globe.js` | Las dos pruebas de globo (ligero con d3 y pesado con WebGL) |

## Aviso antes de republicar

Las fotos que se guardan desde el mapa publicado viven **solo en el Artifact**, no en este repo. Antes de republicar hay que leer la versión publicada, sacar su bloque `photos-data` a un `fotos.json` y compilar con `python build.py fotos.json`. Si no, se pierden.

© 2026 Iñigo Caraballo. Todos los derechos reservados.
