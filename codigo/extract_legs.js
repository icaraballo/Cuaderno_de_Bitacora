// Extrae de template.html los tramos (coche, bus, tren) con sus coordenadas, en JSON.
// Uso: node extract_legs.js template.html > legs.json
const fs = require('fs');
const t = fs.readFileSync(process.argv[2], 'utf8');
const a = t.indexOf('const PLACES={');
const b = t.indexOf('/* ───', t.indexOf('const TRIPS=['));
const { PLACES, TRIPS } = new Function(t.slice(a, b) + '; return {PLACES, TRIPS};')();
const out = [];
for (const trip of TRIPS) {
  for (let i = 1; i < trip.stops.length; i++) {
    const s0 = trip.stops[i - 1], s1 = trip.stops[i];
    out.push({ trip: trip.id, i, mode: s1.mode, from: s0.p, to: s1.p,
      a: PLACES[s0.p].ll, b: PLACES[s1.p].ll, an: PLACES[s0.p].n, bn: PLACES[s1.p].n });
  }
}
process.stdout.write(JSON.stringify(out));
