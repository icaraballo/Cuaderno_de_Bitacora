"""Genera mapa-de-viajes.html a partir de template.html.
Uso: python3 build.py [fotos.json]   (fotos.json = fotos ya guardadas en la página publicada)
Si existe routes.json (salida de build_routes.py), se incrusta como ROUTES dentro del script principal.
El mapa del mundo (50m) y el sencillo del globo (110m) salen de node_modules/world-atlas (npm i world-atlas@2) o, si no está, de topo.json y topo110.json."""
import json,os,re,sys

t=open('template.html',encoding='utf-8').read()
LIBS=('<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>\n'
      '<script src="https://cdnjs.cloudflare.com/ajax/libs/topojson/3.0.2/topojson.min.js"></script>\n')
assert LIBS in t,'libs block changed'
marker='<style id="app-style">'
head=t[:t.index(marker)]

def jsstr(s):
    return json.dumps(s,ensure_ascii=False).replace('</','<\\/')

photos='{}'
if len(sys.argv)>1:
    photos=json.dumps(json.load(open(sys.argv[1],encoding='utf-8')),separators=(',',':'),ensure_ascii=False).replace('<','\\u003c')

routes='{}'
if '__ROUTES__' in t and os.path.exists('routes.json'):
    routes=json.dumps(json.load(open('routes.json',encoding='utf-8')),separators=(',',':'),ensure_ascii=False)

if os.path.exists('node_modules/world-atlas/countries-50m.json'):
    d=json.load(open('node_modules/world-atlas/countries-50m.json'))
    d['objects']={'countries':d['objects']['countries']}
    topo=json.dumps(d,separators=(',',':'))
else:
    topo=open('topo.json',encoding='utf-8').read().strip()
# mapa sencillo (110m) para el globo
if os.path.exists('node_modules/world-atlas/countries-110m.json'):
    d=json.load(open('node_modules/world-atlas/countries-110m.json'))
    d['objects']={'countries':d['objects']['countries']}
    topo_lo=json.dumps(d,separators=(',',':'))
else:
    topo_lo=open('topo110.json',encoding='utf-8').read().strip()
out=(t.replace('__TOPO_JSON__',topo)
      .replace('__TOPO_LO__',topo_lo)
      .replace('__PHOTOS__',photos)
      .replace('__ROUTES__',routes)
      .replace('__HEAD__',jsstr(head))
      .replace('__LIBS__',jsstr(LIBS)))
assert not re.findall(r'__(?:HEAD|LIBS|PHOTOS|TOPO_JSON|TOPO_LO|ROUTES)__',out)

main=re.search(r'<script id="main-js">(.*?)</script>',out,re.S).group(1)
assert '</script' not in main and '<!--' not in main,'main script would break the page'
open('main.js','w',encoding='utf-8').write(main)
open('mapa-de-viajes.html','w',encoding='utf-8').write(out)
print('built',len(out)//1024,'KB')
