// Read-only extractor: loads game data files from a9b21f0 (git archive in /tmp/a9) into a VM, dumps JSON.
const fs=require('fs'),vm=require('vm');const R=process.argv[2]||'/tmp/a9/js/';
const G={};const c=vm.createContext({G,window:{G},console,performance:{now:()=>0},Math});
for(const f of ['core/util.js','data/pokedex.js','data/sprites-meta.js','data/types.js','data/moves.js','data/upgrades.js','data/starters.js'])vm.runInContext(fs.readFileSync(R+f,'utf8'),c);
// sprites.js bodyRadius/hovers need meta only; reimplement exactly (sprites.js:14,20,127-131)
const meta=d=>G.SPRITE_META[d];const PX=2;
const animMeta=(d,a)=>{const m=meta(d);if(!m)return null;return (m.a&&m.a[a])||null};
const bodyRadius=d=>{const m=animMeta(d,'Idle');const w=m?m.w:32;return Math.min(26,Math.max(5,w*0.22))*PX};
const hovers=d=>{const m=meta(d);return !!(m&&m.hv)};
G.Sprites={hovers,bodyRadius};
vm.runInContext(fs.readFileSync(R+'data/enemies.js','utf8').replace(/return \{\s*TIERS,/,'return { behaviorOf, defFor, TIERS,'),c);
const E=G.Enemies;
const tiers=E.TIERS.map((t,ti)=>({...t,cands:E.candidates(t).map(p=>({dex:p.dex,types:p.types,beh:E.behaviorOf(p),def:E.defFor(p,t,ti),r:bodyRadius(p.dex),fly:hovers(p.dex)}))}));
const mv=G.Moves;const moves={};
for(const m of mv.ALL){const L=[];for(let l=1;l<=m.maxLvl;l++){const s=mv.instance(m.id,l);delete s.def;L.push(s)}
 let ev=null;if(m.kind!=='buff'){const s=mv.instance(m.id,m.maxLvl);if(mv.evolve(s)){delete s.def;ev=s}}
 const e=mv.evoInfo({id:m.id,kind:m.kind,lvl:m.maxLvl,def:m},{});
 moves[m.id]={id:m.id,name:m.name,type:m.type,kind:m.kind,maxLvl:m.maxLvl,levels:L,evo:ev,needs:e?e.needs:null}}
const dex=G.DEX.map(p=>({dex:p.dex,name:p.name,types:p.types,hp:p.hp,spd:p.spd,atk:p.atk,rarity:p.rarity,leg:!!p.leg,bst:p.bst,r:bodyRadius(p.dex),start:G.startMoveOf(p.dex),pool:mv.poolFor(p)}));
const T=Object.keys(G.Types.CHART);const chart={};for(const a of T){chart[a]={};for(const d of T)chart[a][d]=G.Types.mult(a,[d])}
fs.writeFileSync('v3_data.json',JSON.stringify({tiers,bosses:E.BOSS_SLOTS,moves,dex,chart,upgrades:G.Upgrades?G.Upgrades.LIST||null:null}));
console.log(dex.length,Object.keys(moves).length,tiers.map(t=>t.cands.length).join(','),Object.keys(G).join(','));
// dual-type multipliers exactly as types.js mult() (SOFT + clamp)
const combos=new Set(G.DEX.map(p=>p.types.join('/')));const tm={};
for(const a of T){tm[a]={};for(const k of combos)tm[a][k]=G.Types.mult(a,k.split('/'))}
const all=JSON.parse(fs.readFileSync('v3_data.json'));all.tmult=tm;
const U=fs.readFileSync(R+'data/upgrades.js','utf8');all.upgrades_src_ok=/max: 10, base: 80/.test(U);
fs.writeFileSync('v3_data.json',JSON.stringify(all));console.log('tmult',Object.keys(tm).length,combos.size);
