"""Calcula rutas reales (coche/bus por carretera, tren por vía) con datos abiertos de Natural Earth.
Uso: python3 build_routes.py legs.json ne_dir routes.json [--report]
- Red de carreteras: ne_10m_roads (solo carreteras principales). Red de ferrocarril: ne_10m_railroads.
- Cada tramo se engancha a la red por su punto más cercano y se busca el camino más corto (Dijkstra).
- Si el tramo no se puede enganchar bien a la red, se deja fuera de routes.json y la página lo dibuja en arco.
"""
import json, math, sys
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

legs_file, ne_dir, out_file = sys.argv[1:4]
REPORT = '--report' in sys.argv

LAYER = {'car': 'road', 'bus': 'road', 'train': 'rail'}
FILES = {'road': 'ne_10m_roads', 'rail': 'ne_10m_railroads'}
SNAP_MAX = {'road': 30.0, 'rail': 30.0}      # km: distancia máxima del lugar a la red
DETOUR_MAX = 2.2                              # ruta / línea recta máximo aceptable (tramos largos)
SIMPLIFY = 0.006                              # grados (~650 m)
PAD = 1.2                                     # grados de margen alrededor de cada tramo para el grafo
BRIDGE_KM = 9.0                               # une tramos de red separados hasta esta distancia (huecos de los datos)
CELL = 0.004                                  # grados (~400 m): vértices más cercanos se funden en un nodo
R = 6371.0
# factor de coste por tipo de carretera: favorece las vías principales
ROAD_COST = {'Major Highway': 1.0, 'Secondary Highway': 1.2, 'Beltway': 1.1, 'Bypass': 1.1, 'Road': 1.5}


def hav(lon1, lat1, lon2, lat2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2 - lon1)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def xyz(lon, lat):
    la, lo = np.radians(lat), np.radians(lon)
    return np.column_stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])


def lines_of(g):
    if g['type'] == 'LineString':
        yield g['coordinates']
    elif g['type'] == 'MultiLineString':
        yield from g['coordinates']


def dp(pts, tol):
    """Douglas-Peucker iterativo sobre una polilínea (array Nx2 en grados)."""
    n = len(pts)
    if n < 3:
        return list(range(n))
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = pts[i], pts[j]
        seg = pts[i + 1:j]
        ab = b - a
        L2 = float(ab @ ab)
        if L2 == 0:
            d = np.hypot(*(seg - a).T)
        else:
            t = np.clip(((seg - a) @ ab) / L2, 0, 1)
            proj = a + t[:, None] * ab
            d = np.hypot(*(seg - proj).T)
        k = int(np.argmax(d))
        if d[k] > tol:
            m = i + 1 + k
            keep[m] = True
            stack.append((i, m))
            stack.append((m, j))
    return np.nonzero(keep)[0]


legs = json.load(open(legs_file, encoding='utf-8'))
want = [l for l in legs if l['mode'] in LAYER]
# tramos únicos por capa y par de lugares (sin dirección)
uniq = {}
for l in want:
    layer = LAYER[l['mode']]
    a, b = sorted([l['from'], l['to']])
    key = layer + '|' + a + '|' + b
    if key not in uniq:
        src, dst = (l['a'], l['b']) if l['from'] == a else (l['b'], l['a'])
        uniq[key] = dict(layer=layer, a=a, b=b, pa=src, pb=dst, names=(l['an'] if l['from'] == a else l['bn'], l['bn'] if l['from'] == a else l['an']), uses=[])
    uniq[key]['uses'].append(l['trip'] + ':' + l['mode'])

print('tramos a calcular:', len(want), '| únicos:', len(uniq), file=sys.stderr)

routes, report = {}, []
for layer in ('road', 'rail'):
    mine = {k: u for k, u in uniq.items() if u['layer'] == layer}
    if not mine:
        continue
    boxes = []
    for u in mine.values():
        lo0, la0 = min(u['pa'][0], u['pb'][0]) - PAD, min(u['pa'][1], u['pb'][1]) - PAD
        lo1, la1 = max(u['pa'][0], u['pb'][0]) + PAD, max(u['pa'][1], u['pb'][1]) + PAD
        boxes.append((lo0, lo1, la0, la1))
    gj = json.load(open(f"{ne_dir}/{FILES[layer]}.geojson", encoding='utf-8'))
    segs_u, segs_v, segs_c = [], [], []   # vértices (lon,lat) enlazados + coste
    P = []   # todos los vértices
    E = []   # pares de índices consecutivos
    C = []   # factor de coste
    for f in gj['features']:
        props = f['properties']
        ty = (props.get('type') or '') if layer == 'road' else ''
        if layer == 'road' and 'ferry' in ty.lower():
            continue
        fac = ROAD_COST.get(ty, 1.5) if layer == 'road' else 1.0
        for line in lines_of(f['geometry']):
            if len(line) < 2:
                continue
            arr = np.asarray([c[:2] for c in line], float)
            # descarta líneas completamente fuera de todas las cajas
            lo, la = arr[:, 0], arr[:, 1]
            inside = np.zeros(len(arr), bool)
            for (lo0, lo1, la0, la1) in boxes:
                inside |= (lo >= lo0) & (lo <= lo1) & (la >= la0) & (la <= la1)
            if not inside.any():
                continue
            base = len(P)
            P.extend(arr.tolist())
            idx = np.arange(base, base + len(arr))
            E.append(np.column_stack([idx[:-1], idx[1:]]))
            C.append(np.full(len(arr) - 1, fac))
    P = np.asarray(P)
    E = np.vstack(E)
    C = np.concatenate(C)
    print(f'[{layer}] vértices en cajas: {len(P)} | segmentos: {len(E)}', file=sys.stderr)

    # nodos: funde vértices en celdas
    key = np.round(P[:, 0] / CELL).astype(np.int64) * 1000003 + np.round(P[:, 1] / CELL).astype(np.int64)
    uk, inv = np.unique(key, return_inverse=True)
    nn = len(uk)
    cnt = np.bincount(inv, minlength=nn)
    NX = np.bincount(inv, weights=P[:, 0], minlength=nn) / cnt
    NY = np.bincount(inv, weights=P[:, 1], minlength=nn) / cnt
    u, v = inv[E[:, 0]], inv[E[:, 1]]
    ok = u != v
    u, v, c = u[ok], v[ok], C[ok]
    w = hav(NX[u], NY[u], NX[v], NY[v]) * c
    # aristas únicas con el menor coste
    a_, b_ = np.minimum(u, v), np.maximum(u, v)
    order = np.lexsort((w, b_, a_))
    a_, b_, w = a_[order], b_[order], w[order]
    first = np.ones(len(a_), bool)
    first[1:] = (a_[1:] != a_[:-1]) | (b_[1:] != b_[:-1])
    a_, b_, w = a_[first], b_[first], w[first]
    print(f'[{layer}] nodos: {nn} | aristas: {len(a_)}', file=sys.stderr)

    # puentes entre nodos cercanos (cruces sin vértice compartido)
    tree = cKDTree(xyz(NX, NY))
    pairs = tree.query_pairs(BRIDGE_KM / R, output_type='ndarray')
    if len(pairs):
        pd_ = hav(NX[pairs[:, 0]], NY[pairs[:, 0]], NX[pairs[:, 1]], NY[pairs[:, 1]])
        # salto corto (cruce sin vértice compartido): barato; salto largo (hueco en los datos): caro
        pw = pd_ * np.where(pd_ < 2.0, 2.0, 3.5) + 0.05
        a_ = np.concatenate([a_, pairs[:, 0]]); b_ = np.concatenate([b_, pairs[:, 1]]); w = np.concatenate([w, pw])
    print(f'[{layer}] puentes: {len(pairs)}', file=sys.stderr)

    G = csr_matrix((np.concatenate([w, w]), (np.concatenate([a_, b_]), np.concatenate([b_, a_]))), shape=(nn, nn))
    # si hay aristas duplicadas, csr las suma: se limita a la mínima rehaciendo desde coo ordenado
    G.sum_duplicates()

    for key_, uu in mine.items():
        pa, pb = uu['pa'], uu['pb']
        da, ia = tree.query(xyz(np.array([pa[0]]), np.array([pa[1]]))[0])
        db, ib = tree.query(xyz(np.array([pb[0]]), np.array([pb[1]]))[0])
        da_km, db_km = da * R, db * R
        straight = float(hav(pa[0], pa[1], pb[0], pb[1]))
        row = dict(key=key_, names=uu['names'], layer=layer, straight=round(straight), snap_a=round(da_km, 1), snap_b=round(db_km, 1), uses=sorted(set(uu['uses'])))
        if da_km > SNAP_MAX[layer] or db_km > SNAP_MAX[layer]:
            row.update(status='fallback', why='lejos de la red')
            report.append(row); continue
        if ia == ib:
            row.update(status='fallback', why='mismo nodo')
            report.append(row); continue
        dist, pred = dijkstra(G, directed=False, indices=int(ia), return_predecessors=True)
        if not np.isfinite(dist[ib]):
            row.update(status='fallback', why='sin conexión en la red')
            report.append(row); continue
        path = [int(ib)]
        while path[-1] != int(ia):
            path.append(int(pred[path[-1]]))
        path.reverse()
        poly = np.column_stack([NX[path], NY[path]])
        poly = np.vstack([[pa], poly, [pb]])
        # simplifica con escala lon*cos(lat) para no deformar
        cl = math.cos(math.radians((pa[1] + pb[1]) / 2))
        sc = np.column_stack([poly[:, 0] * cl, poly[:, 1]])
        keep = dp(sc, SIMPLIFY)
        poly = poly[keep]
        km = float(np.sum(hav(poly[:-1, 0], poly[:-1, 1], poly[1:, 0], poly[1:, 1])))
        ratio = km / max(straight, 1e-6)
        row.update(km=round(km), ratio=round(ratio, 2), pts=len(poly))
        if ratio > DETOUR_MAX and (km - straight) > 12:
            row.update(status='fallback', why=f'rodeo excesivo ({ratio:.1f}×)')
            report.append(row); continue
        row.update(status='ok')
        report.append(row)
        routes[key_] = dict(p=[round(float(x), 3) for x in poly.ravel()], km=round(km, 1))

json.dump(routes, open(out_file, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
ok = [r for r in report if r['status'] == 'ok']
print(f'\nrutas reales: {len(ok)} de {len(report)} | tamaño routes.json: {len(json.dumps(routes, separators=(",", ":")))//1024} KB', file=sys.stderr)
if REPORT:
    for r in sorted(report, key=lambda r: (r['status'], r['key'])):
        print(r['status'].ljust(8), r['key'].ljust(34), f"recta {r['straight']:>5} km", f"snap {r['snap_a']}/{r['snap_b']} km", ('ruta ' + str(r.get('km')) + ' km ×' + str(r.get('ratio'))) if r.get('km') else '', r.get('why', ''))
json.dump(report, open(out_file.replace('.json', '.report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
