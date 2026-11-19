const fs=require('fs');const s=fs.readFileSync(process.argv[2],'utf8');
const grab=(k,e)=>{const a=s.indexOf(k);const b=s.indexOf(e,a);return s.slice(a+k.length,b+e.length-1);};
const PLACES=eval('('+grab('const PLACES=','\n};')+')');
const TRIPS=eval('('+grab('const TRIPS=','\n];')+')');
const routes=JSON.parse(fs.readFileSync('routes.json','utf8'));
const LAYER={car:'road',bus:'road',train:'rail'};
const out={trips:[],iso:[]};const iso=new Set();
for(const t of TRIPS){
  const legs=[];
  for(let i=1;i<t.stops.length;i++){
    const a=t.stops[i-1].p,b=t.stops[i].p,m=t.stops[i].mode;
    const L={m,a,b};
    const lay=LAYER[m];
    if(lay){const rev=a>b,r=routes[lay+'|'+(rev?b+'|'+a:a+'|'+b)];
      if(r){let p=[];for(let j=0;j<r.p.length;j+=2)p.push([r.p[j],r.p[j+1]]);if(rev)p.reverse();L.r=p;}}
    legs.push(L);
  }
  t.stops.slice(1,-1).forEach(st=>{if(!st.layover)iso.add(PLACES[st.p].iso);});
  out.trips.push({id:t.id,y:t.year,title:t.title,short:t.short||t.title,legs});
}
out.places={};for(const k in PLACES)out.places[k]={n:PLACES[k].n,ll:PLACES[k].ll};
out.iso=[...iso];
fs.writeFileSync('globe-data.json',JSON.stringify(out));
console.log(out.trips.length,out.iso.length,JSON.stringify(out).length);
