"""
render_clinical.py — clinical symptoms page body for the Epidemic Dashboard.

Loads clinical_data.json + clinical_fits.json from Processed_Sensitive_Data
(outputs/clinical_symptoms_manifest.json → dated clinical_symptoms/), and
assembles an HTML page that shares the dashboard nav chrome.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
LOGO_PATH = HERE / "LOGO_SITE-1.png"

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"
JSPDF_CDN = "https://cdn.jsdelivr.net/npm/jspdf@2.5.2/dist/jspdf.umd.min.js"


def _resolve_plots_root() -> Path:
    env = os.environ.get("DASHBOARD_PLOTS_DIR", "").strip()
    if env:
        return Path(env).resolve()
    return (REPO_ROOT.parent / "BDBV2026-Processed_Sensitive_Data" / "outputs").resolve()


def load_clinical_bundle(plots_root: Path | None = None) -> tuple[dict, dict, Path]:
    """Return (DATA, FITS, clinical_dir). Raises FileNotFoundError if missing."""
    root = plots_root or _resolve_plots_root()
    manifest_path = root / "clinical_symptoms_manifest.json"
    if manifest_path.is_file():
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        clin_dir = root / m["path"]
    else:
        # Fallback: newest outputs/*/clinical_symptoms with clinical_data.json
        candidates = sorted(
            (p for p in root.glob("*/clinical_symptoms") if (p / "clinical_data.json").is_file()),
            key=lambda p: p.parent.name,
            reverse=True,
        )
        if not candidates:
            raise FileNotFoundError(f"No clinical_symptoms artifacts under {root}")
        clin_dir = candidates[0]
    data_path = clin_dir / "clinical_data.json"
    fits_path = clin_dir / "clinical_fits.json"
    if not data_path.is_file():
        raise FileNotFoundError(data_path)
    if not fits_path.is_file():
        raise FileNotFoundError(fits_path)
    data = json.loads(data_path.read_text(encoding="utf-8"))
    fits = json.loads(fits_path.read_text(encoding="utf-8"))
    return data, fits, clin_dir


LOGO_B64 = base64.b64encode(LOGO_PATH.read_bytes()).decode() if LOGO_PATH.is_file() else ""

CSS = r"""
:root{
  --bg:#eef3f7; --panel:#ffffff; --panel2:#f3f7fa; --ink:#16283d; --muted:#5f7488;
  --line:#d8e2ec; --navy:#0f3c6b; --accent:#1c6bb0; --accent2:#178a6e;
  --gold:#d9a13b; --bad:#c0392b; --chip:#eaf1f7;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  font-size:14px;line-height:1.45}
a{color:var(--accent)}
header{padding:16px 26px 12px;border-bottom:3px solid var(--navy);background:#fff}
header h1{margin:0 0 3px;font-size:20px;letter-spacing:.2px;color:var(--navy)}
header .sub{color:var(--muted);font-size:13px}
header .sub b{color:var(--ink)}
.hbrand{display:flex;align-items:center;gap:16px}
.hlogo{height:52px;width:auto;display:block;flex:none}
.hbrand .htxt{flex:1;min-width:0}
.horg{flex:none;text-align:right;color:var(--navy);font-size:12px;font-weight:700;line-height:1.35;max-width:210px}
.horg span{display:block;color:var(--muted);font-weight:400;font-size:10.5px;margin-top:2px}
@media(max-width:680px){.horg{display:none}.hlogo{height:42px}}
.datacut{display:inline-block;margin-top:7px;background:var(--navy);color:#fff;font-size:12.5px;
  font-weight:600;letter-spacing:.3px;padding:4px 11px;border-radius:6px}
.datacut span{opacity:.75;font-weight:400}

.clinical-title-block{padding:16px 26px 12px;border-bottom:3px solid var(--navy);background:#fff}
.clinical-title-block h1{margin:0 0 6px;font-size:20px;letter-spacing:.2px;color:var(--navy)}
.clinical-title-block .sub{color:var(--muted);font-size:13px;max-width:1100px}
.clinical-title-block .sub b{color:var(--ink)}
.wrap{max-width:1280px;margin:0 auto;padding:0 20px 70px}
.filterbar{flex:0 0 auto;position:relative;z-index:30;background:rgba(255,255,255,.98);
  backdrop-filter:blur(6px);border-bottom:1px solid var(--line);padding:11px 26px;
  display:flex;gap:16px;align-items:flex-end;flex-wrap:wrap;box-shadow:0 1px 4px rgba(15,60,107,.06)}
.clinical-body{flex:1 1 auto;min-height:0;overflow:auto;-webkit-overflow-scrolling:touch}
.fgroup{display:flex;flex-direction:column;gap:4px}
.fgroup label{font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted)}
.info{display:inline-flex;align-items:center;justify-content:center;width:13px;height:13px;border-radius:50%;
  background:var(--muted);color:#fff;font-size:9px;font-weight:700;font-style:italic;cursor:help;margin-left:5px;position:relative}
.info:hover::after{content:attr(data-tip);position:absolute;left:17px;top:-6px;width:270px;white-space:normal;
  background:var(--ink);color:#fff;padding:8px 11px;border-radius:7px;font-size:11.5px;font-weight:400;
  line-height:1.45;z-index:60;box-shadow:0 3px 12px rgba(15,60,107,.28);text-transform:none;letter-spacing:0}
.gloss{border-bottom:1px dotted var(--accent);cursor:help;position:relative}
.gloss:hover::after{content:attr(data-tip);position:absolute;left:0;top:1.4em;width:280px;white-space:normal;
  background:var(--ink);color:#fff;padding:8px 11px;border-radius:7px;font-size:11.5px;font-weight:400;
  line-height:1.45;z-index:60;box-shadow:0 3px 12px rgba(15,60,107,.28)}
.note.triage{border-left-color:var(--accent)}
select[multiple]{min-width:135px;max-width:200px;height:74px;background:#fff;
  color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:4px;font-size:12.5px}
select.one{background:#fff;color:var(--ink);border:1px solid var(--line);border-radius:7px;
  padding:6px 9px;font-size:12.5px}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:7px;overflow:hidden}
.seg button{background:#fff;color:var(--muted);border:0;padding:8px 12px;cursor:pointer;font-size:12.5px}
.seg button.on{background:var(--accent);color:#fff;font-weight:600}
.btn{background:var(--chip);color:var(--navy);border:1px solid var(--line);border-radius:7px;
  padding:8px 13px;cursor:pointer;font-size:12.5px}
.btn:hover{border-color:var(--accent)}
.nrec{margin-left:auto;color:var(--muted);font-size:12.5px;align-self:center}
.nrec b{color:var(--accent);font-size:15px}
section{margin:28px 0 6px}
.sfxhead{display:flex;align-items:baseline;gap:12px;margin-bottom:2px;flex-wrap:wrap}
.sfxhead h2{font-size:16px;margin:0;color:var(--navy)}
.sfxhead .n{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.7px}
.sfxhead .ctl{margin-left:auto;display:flex;gap:10px;align-items:center}
.sfxhead .ctl label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.desc{color:var(--muted);font-size:12.5px;margin:0 0 10px;max-width:960px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px 12px 6px;
  box-shadow:0 1px 3px rgba(15,60,107,.05);position:relative}
.figdl{position:absolute;top:7px;right:9px;display:flex;gap:4px;opacity:.35;transition:opacity .15s;z-index:6}
.panel:hover .figdl{opacity:1}
.figdl button{background:var(--chip);border:1px solid var(--line);color:var(--navy);border-radius:5px;
  padding:2px 7px;font-size:10px;font-weight:700;letter-spacing:.3px;cursor:pointer}
.figdl button:hover{border-color:var(--accent);background:#fff}
.figdl button:disabled{opacity:.5;cursor:progress}
.ptitle{font-size:13.5px;font-weight:600;color:var(--navy);padding:4px 6px 0}
.ptitle span{display:block;font-weight:400;font-size:11.5px;color:var(--muted)}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:13px 15px;
  box-shadow:0 1px 3px rgba(15,60,107,.05)}
.kpi .v{font-size:23px;font-weight:700;letter-spacing:.3px;color:var(--navy)}
.kpi .k{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.5px;margin-top:2px}
.kpi .s{color:var(--muted);font-size:11px;margin-top:3px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
.chart{width:100%}
.cap{color:var(--muted);font-size:12px;padding:2px 6px 8px}
.cap b{color:var(--ink)}
.note{background:var(--panel2);border-left:3px solid var(--gold);border-radius:6px;
  padding:9px 13px;color:var(--muted);font-size:12.5px;margin:10px 0}
.note b{color:var(--ink)}
.supp{background:#f7f5ee;border:1px solid #e6dcc2}
table.tbl{border-collapse:collapse;font-size:12.5px;margin:4px 0;width:100%}
table.tbl th,table.tbl td{border:1px solid var(--line);padding:5px 9px;text-align:right;white-space:nowrap}
table.tbl th:first-child,table.tbl td:first-child{text-align:left}
table.tbl thead th{background:var(--panel2);color:var(--navy);position:sticky;top:0}
table.tbl tr:hover td{background:#f6f9fc}
.pos{color:var(--bad)} .neg{color:var(--accent2)}
.tblwrap{max-height:640px;overflow:auto;border:1px solid var(--line);border-radius:10px}
.fitbadge{font-size:10.5px;padding:1px 6px;border-radius:5px;background:#eef7f2;color:var(--accent2);font-weight:600}
#errbar{display:none;background:#fdecea;color:#a33;padding:8px 26px;font-size:12.5px;
  border-bottom:1px solid #f5c6c0;font-family:monospace}
@media(max-width:1100px){.kpis{grid-template-columns:repeat(3,1fr)}.grid3{grid-template-columns:1fr}}
@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}}
"""

JS = r"""
const DATA=__DATA__, FITS=__FITS__;
const LOGO="data:image/png;base64,__LOGO__";
const LOGOIMG=new Image(); LOGOIMG.src=LOGO;
const M=DATA.meta, R=DATA.rec, ADJ=DATA.adj_rr, N=R.on.length;
const CHROME=(function(){try{const el=document.getElementById('clinical-chrome-payload');
  return el?JSON.parse(el.textContent):{};}catch(e){return {};}})();
const I18N=CHROME.i18n||{};
let currentLang=(function(){const s=localStorage.getItem('bdbv-dashboard-lang');
  if(s&&I18N.strings&&I18N.strings[s])return s;
  const nav=(navigator.language||'').slice(0,2).toLowerCase();
  if(nav==='fr'&&I18N.strings&&I18N.strings.fr)return 'fr';
  return (I18N.default||'en');})();
function t(path){const parts=String(path).split('.');
  let node=(I18N.strings&&I18N.strings[currentLang])||(I18N.strings&&I18N.strings.en)||{};
  for(let i=0;i<parts.length;i++){if(node==null||typeof node!=='object')return path;node=node[parts[i]];}
  return node!=null?node:path;}
function tf(path,vars){let s=String(t(path));if(vars)Object.keys(vars).forEach(k=>{s=s.split('{'+k+'}').join(String(vars[k]));});return s;}
function localeTag(){return currentLang==='fr'?'fr-FR':'en-US';}
function symLabel(i){const code=M.sym_codes[i];const tr=t('clinical.sym.'+code);
  return (tr&&tr!==('clinical.sym.'+code))?tr:(M.sym_labels[i]||code);}
let SYML=M.sym_labels.slice();
function refreshSymLabels(){SYML=M.sym_codes.map((_,i)=>symLabel(i));}
function applyClinicalStaticI18n(){
  document.documentElement.lang=currentLang;
  document.querySelectorAll('[data-i18n]').forEach(el=>{
    const key=el.getAttribute('data-i18n'); const val=t(key);
    if(val&&val!==key){ if(el.tagName==='OPTION') el.textContent=val; else el.textContent=val; }
  });
  document.querySelectorAll('[data-i18n-html]').forEach(el=>{
    const key=el.getAttribute('data-i18n-html'); const val=t(key);
    if(val&&val!==key) el.innerHTML=val;
  });
  const title=document.querySelector('.clinical-title-block h1');
  if(title) title.textContent=t('clinical.title');
  const sub=document.getElementById('clinical-subtitle');
  if(sub) sub.innerHTML=tf('clinical.subtitle',{
    nscope:Number(M.n_scope).toLocaleString(localeTag()),
    nraw:Number(M.n_raw).toLocaleString(localeTag()),
    generated:M.generated||M.snapshot
  });
  const headSub=document.getElementById('title-sub');
  if(headSub) headSub.innerHTML=tf('clinical.header_sub',{snap:M.snapshot});
  const scopeNote=document.getElementById('clinical-scope-note');
  if(scopeNote) scopeNote.innerHTML=t('clinical.scope_note');
  const langSwitcher=document.getElementById('lang-switcher');
  if(langSwitcher) langSwitcher.classList.toggle('lang-fr', currentLang==='fr');
  document.querySelectorAll('.lang-btn').forEach(btn=>{
    const on=btn.dataset.lang===currentLang;
    btn.classList.toggle('active',on); btn.setAttribute('aria-pressed',on?'true':'false');
  });
}
function updateLegalContent(){
  const methods=(I18N.methods_html||{})[currentLang]||CHROME.methods_html||'';
  const terms=(I18N.terms_html||{})[currentLang]||CHROME.terms_html||'';
  const updated=((I18N.terms_updated||{})[currentLang])||CHROME.terms_updated||'';
  const mc=document.getElementById('methods-content');
  const tc=document.getElementById('terms-content');
  if(mc) mc.innerHTML=methods||('<p style="color:#888">'+t('ui.methods_missing')+'</p>');
  if(tc) tc.innerHTML=terms||('<p style="color:#888">'+t('ui.terms_missing')+'</p>');
  const tu=document.getElementById('terms-updated');
  if(tu) tu.textContent=updated?(t('ui.terms_updated')+' '+updated):'';
}
function buildPartners(){
  const partners=CHROME.partners||[]; const root=document.getElementById('partners');
  if(!root) return;
  if(!partners.length){root.style.display='none';return;}
  root.innerHTML=partners.map(p=>{
    const img='<img src="'+p.src+'" alt="'+(p.alt||'')+'" title="'+(p.alt||'')+'" />';
    return p.url?('<a href="'+p.url+'" target="_blank" rel="noopener">'+img+'</a>'):img;
  }).join('');
}
function wireChrome(){
  function openModal(id){const m=document.getElementById(id); if(m) m.classList.add('open');}
  function closeModal(id){const m=document.getElementById(id); if(m) m.classList.remove('open');}
  const mb=document.getElementById('methods-btn'); if(mb) mb.addEventListener('click',()=>openModal('methods-modal'));
  const tb=document.getElementById('terms-btn'); if(tb) tb.addEventListener('click',()=>openModal('terms-modal'));
  const mc=document.getElementById('methods-close'); if(mc) mc.addEventListener('click',()=>closeModal('methods-modal'));
  const tc=document.getElementById('terms-close'); if(tc) tc.addEventListener('click',()=>closeModal('terms-modal'));
  document.querySelectorAll('.lang-btn').forEach(btn=>{
    btn.addEventListener('click',()=>{
      const lang=btn.dataset.lang||'en';
      if(!I18N.strings||!I18N.strings[lang]) return;
      currentLang=lang; localStorage.setItem('bdbv-dashboard-lang',lang);
      refreshSymLabels(); applyClinicalStaticI18n(); updateLegalContent(); renderAll();
    });
  });
  buildPartners(); updateLegalContent();
}
const DAY=86400000, EPOCH=Date.parse(M.epoch);
const SNAP=Math.round((Date.parse(M.snapshot)-EPOCH)/DAY);
const ONSET_MIN=Math.round((Date.parse(M.onset_min)-EPOCH)/DAY);
const SYMC=M.sym_codes, NS=SYMC.length;
// Display order: least severe / most generic → most severe / least generic.
// Bit indices in R.sym stay as in M.sym_codes; SYM_ORDER remaps for UI only.
const SYM_SEVERITY=[
  'FAT','AN','FV','CEP','DART','DM','AU',
  'DA','DIA','VOM',
  'TX','MG','CONJ','EC','DRO','DT','HQ',
  'DAV','DR','ICT',
  'SH','CONF','COMA'
];
function buildSymOrder(){
  const rank=Object.fromEntries(SYM_SEVERITY.map((c,i)=>[c,i]));
  return [...Array(NS).keys()].sort((a,b)=>{
    const ra=rank[SYMC[a]], rb=rank[SYMC[b]];
    const ua=ra==null, ub=rb==null;
    if(ua!==ub) return ua?1:-1;
    if(!ua && ra!==rb) return ra-rb;
    return a-b;
  });
}
const SYM_ORDER=buildSymOrder();
function symRank(code){
  const i=SYM_SEVERITY.indexOf(code);
  return i<0?SYM_SEVERITY.length+SYMC.indexOf(code):i;
}
refreshSymLabels();
function d2s(d){return new Date(EPOCH+d*DAY).toISOString().slice(0,10);}

// ---------- palette (INRB) ----------
const PAL=['#0f3c6b','#1c6bb0','#178a6e','#d9a13b','#7a4fa3','#4a9bd4','#3f9e6c',
           '#c0663b','#5c7a99','#b0447a','#2aa0a8','#8a9a2b'];
const statusColor={positive:'#c0392b', negative:'#3f9e6c'};
const vitalColor ={'died':'#c0392b','no death recorded':'#5c7a99'};
const sexColor   ={female:'#b0447a', male:'#2c7fb8'};
const hcwColor   ={'non-HCW':'#5c7a99','healthcare worker':'#d9a13b'};
const abColor    =i=>PAL[i%PAL.length];
const famcol     ={lognormal:'#1c6bb0',gamma:'#178a6e',weibull:'#d9a13b'};

const PLBASE={paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',
  font:{color:'#2a3b4d',size:12},margin:{l:48,r:16,t:10,b:38},
  xaxis:{gridcolor:'#e2e9f0',zerolinecolor:'#d0dae4',linecolor:'#c4d0dc'},
  yaxis:{gridcolor:'#e2e9f0',zerolinecolor:'#d0dae4',linecolor:'#c4d0dc'},
  legend:{bgcolor:'rgba(255,255,255,0.6)',font:{size:11}}};
const CFG={displayModeBar:false,responsive:true};
function lay(o){return Object.assign(JSON.parse(JSON.stringify(PLBASE)),o);}
function noData(div,h){Plotly.react(div,[],lay({height:h||150,annotations:[{text:t('clinical.labels.no_data'),
  showarrow:false,font:{color:'#8ea3b8'}}],xaxis:{visible:false},yaxis:{visible:false}}),CFG);}

// ---------- stats ----------
function quantile(a,q){if(!a.length)return NaN;const s=[...a].sort((x,y)=>x-y);
  const p=(s.length-1)*q,b=Math.floor(p),r=p-b;
  return s[b+1]!==undefined?s[b]+r*(s[b+1]-s[b]):s[b];}
function mean(a){return a.length?a.reduce((x,y)=>x+y,0)/a.length:NaN;}
function sd(a){if(a.length<2)return NaN;const m=mean(a);return Math.sqrt(a.reduce((s,x)=>s+(x-m)*(x-m),0)/(a.length-1));}
function wilson(x,n){if(!n)return[NaN,NaN];const z=1.96,p=x/n,z2=z*z;
  const c=(p+z2/(2*n))/(1+z2/n), h=z*Math.sqrt(p*(1-p)/n+z2/(4*n*n))/(1+z2/n);return[c-h,c+h];}
function newcombeRD(x1,n1,x0,n0){const p1=x1/n1,p0=x0/n0,[l1,u1]=wilson(x1,n1),[l0,u0]=wilson(x0,n0);
  const rd=p1-p0;return[rd, rd-Math.sqrt((p1-l1)**2+(u0-p0)**2), rd+Math.sqrt((u1-p1)**2+(p0-l0)**2)];}
function katzRR(x1,n1,x0,n0){if(!x1||!x0||!n1||!n0)return null;const rr=(x1/n1)/(x0/n0);
  const se=Math.sqrt(1/x1-1/n1+1/x0-1/n0);return[rr, rr*Math.exp(-1.96*se), rr*Math.exp(1.96*se)];}
function matInv(A){const n=A.length,M2=A.map((r,i)=>[...r,...Array.from({length:n},(_,j)=>i===j?1:0)]);
  for(let c=0;c<n;c++){let pv=c;for(let r=c;r<n;r++)if(Math.abs(M2[r][c])>Math.abs(M2[pv][c]))pv=r;
    if(Math.abs(M2[pv][c])<1e-12)return null;[M2[c],M2[pv]]=[M2[pv],M2[c]];
    const d=M2[c][c];for(let j=0;j<2*n;j++)M2[c][j]/=d;
    for(let r=0;r<n;r++){if(r===c)continue;const f=M2[r][c];for(let j=0;j<2*n;j++)M2[r][j]-=f*M2[c][j];}}
  return M2.map(r=>r.slice(n));}
function ols(X,y){const n=X.length;if(!n)return null;const p=X[0].length;
  const XtX=Array.from({length:p},()=>Array(p).fill(0)),Xty=Array(p).fill(0);
  for(let i=0;i<n;i++){for(let a=0;a<p;a++){Xty[a]+=X[i][a]*y[i];for(let b=0;b<p;b++)XtX[a][b]+=X[i][a]*X[i][b];}}
  const inv=matInv(XtX);if(!inv)return null;const beta=Array(p).fill(0);
  for(let a=0;a<p;a++)for(let b=0;b<p;b++)beta[a]+=inv[a][b]*Xty[b];
  let rss=0;for(let i=0;i<n;i++){let yh=0;for(let a=0;a<p;a++)yh+=X[i][a]*beta[a];rss+=(y[i]-yh)**2;}
  const s2=rss/Math.max(n-p,1);return{beta,se:beta.map((_,a)=>Math.sqrt(s2*inv[a][a])),n};}
function fmtp(p){if(p==null||isNaN(p))return'–';if(p<0.001)return'<0.001';if(p<0.01)return p.toFixed(3);return p.toFixed(2);}
function fillOf(hex,a){const h=hex.replace('#','');return `rgba(${parseInt(h.slice(0,2),16)},${parseInt(h.slice(2,4),16)},${parseInt(h.slice(4,6),16)},${a})`;}

// ---------- filter state ----------
const state={prov:new Set(), ageb:new Set(), sex:'all', hcw:'all', win:'all',
  epiStrat:'sex', symCohort:'confirmed', vital:'union'};
// coherent vital-outcome definition (toggleable): death-alert channel, deceased-at-
// sampling, or the union of the two. "No death recorded" never implies survival.
function diedOf(i){
  if(state.vital==='alert') return R.alert[i]===1;
  if(state.vital==='sampledec') return R.sdec[i]===1;
  return R.alert[i]===1 || R.sdec[i]===1;
}
const BLOOD = (M.sample_types||[]).indexOf('blood');   // ante-mortem specimen for Ct
function coCohort(I){return state.symCohort==='confirmed'?I.filter(i=>R.cc[i]===1):I;}
function selVals(id){return [...document.getElementById(id).selectedOptions].map(o=>+o.value);}
function winDays(){return state.win==='w2'?14:(state.win==='w4'?30:null);}
function inWin(i){const w=winDays();if(w==null)return true;return R.no[i]!=null && R.no[i]>=SNAP-w;}
function passBase(i){
  if(state.prov.size && !state.prov.has(R.p[i])) return false;
  if(state.ageb.size && (R.ab[i]==null || !state.ageb.has(R.ab[i]))) return false;
  if(state.sex!=='all' && R.sex[i]!=+state.sex) return false;
  if(state.hcw!=='all' && R.hcw[i]!=+state.hcw) return false;
  return true;
}
function idx(){const o=[];for(let i=0;i<N;i++)if(passBase(i)&&inWin(i))o.push(i);return o;}

// delay accessors
const DACC={onset_to_admission:{a:'on',b:'hs',win:[0,60],on:true},
            admission_to_exit:{a:'hs',b:'he',win:[0,90],on:false},
            onset_to_death:{a:'on',b:'dh',win:[0,90],on:true}};
function delayVal(i,key){const s=DACC[key],a=R[s.a][i],b=R[s.b][i];
  if(a==null||b==null)return null;if(s.on&&(R.on[i]==null||R.on[i]<ONSET_MIN))return null;
  const d=b-a;return (d>=s.win[0]&&d<=s.win[1])?d:null;}
function hasSym(m,bit){return m!=null && ((m>>bit)&1)===1;}
function testStatus(i){return R.cc[i]===1?'positive':(R.cc[i]===0?'negative':null);}
// HCW privacy: suppress fine-grained / exact small counts (re-identification risk).
const HCW_MIN_N=10;
function hcwCount(I){let n=0;I.forEach(i=>{if(R.hcw[i]===1)n++;});return n;}
function hcwOk(I){return hcwCount(I)>=HCW_MIN_N;}
function hcwLabel(n){return n<HCW_MIN_N?('< '+HCW_MIN_N):String(n);}

// =================================================================== KPIs
function drawKPIs(){
  const I=idx();
  const conf=I.filter(i=>R.cc[i]===1).length, neg=I.filter(i=>R.cc[i]===0).length;
  const unk=I.filter(i=>R.cc[i]!==0&&R.cc[i]!==1).length;
  const pos=(conf+neg)?100*conf/(conf+neg):NaN;
  const died=I.filter(i=>diedOf(i)).length;
  const hosp=I.filter(i=>R.hosp[i]===1).length;
  const hcw=I.filter(i=>R.hcw[i]===1).length;
  const win=state.win==='all'?t('clinical.kpi.win_all'):(state.win==='w2'?t('clinical.kpi.win_14'):t('clinical.kpi.win_30'));
  const cards=[
    [t('clinical.kpi.records'),I.length.toLocaleString(localeTag()),tf('clinical.kpi.records_s',{win:win})],
    [t('clinical.kpi.posneg'),conf.toLocaleString(localeTag())+' / '+neg.toLocaleString(localeTag()),tf('clinical.kpi.posneg_s',{unk:unk.toLocaleString(localeTag())})],
    [t('clinical.kpi.positivity'),isNaN(pos)?'–':pos.toFixed(1)+'%',tf('clinical.kpi.positivity_s',{n:conf+neg})],
    [t('clinical.kpi.deaths'),died.toLocaleString(localeTag()),tf('clinical.kpi.deaths_s',{pct:(100*died/Math.max(I.length,1)).toFixed(1)})],
    [t('clinical.kpi.hosp'),hosp.toLocaleString(localeTag()),t('clinical.kpi.hosp_s')],
    [t('clinical.kpi.hcw'),hcwLabel(hcw),t('clinical.kpi.hcw_s')]];
  document.getElementById('kpis').innerHTML=cards.map(k=>
    `<div class="kpi"><div class="v">${k[1]}</div><div class="k">${k[0]}</div><div class="s">${k[2]}</div></div>`).join('');
}

// =================================================================== data completeness (missing-data reporting)
function drawCompleteness(){
  const I=idx(), n=I.length||1;
  const vars=[
    ['Sex', i=>R.sex[i]!=null],
    ['Age', i=>R.age[i]!=null],
    ['Final classification (test status)', i=>R.cc[i]!=null],
    ['Symptom field', i=>R.sym[i]!=null],
    ['Symptom onset — any date', i=>R.on[i]!=null],
    ['Symptom onset ≥ 15 Jun (reliable)', i=>R.on[i]!=null&&R.on[i]>=ONSET_MIN],
    ['Notification date', i=>R.no[i]!=null],
    ['Hospital admission date', i=>R.hs[i]!=null],
    ['Hospital exit date', i=>R.he[i]!=null],
    ['Sample collection date', i=>R.sa[i]!=null],
    ['Ct — RADIONE (ROE)', i=>R.ctR[i]!=null],
    ['Ct — Altona (PCRA)', i=>R.ctA[i]!=null]];
  const body=vars.map(([lab,f])=>{const c=I.filter(f).length;
    return `<tr><td>${lab}</td><td>${c.toLocaleString()}</td><td>${(100*c/n).toFixed(1)}</td><td>${(I.length-c).toLocaleString()}</td></tr>`;}).join('');
  document.getElementById('completeness').innerHTML=
    `<table class="tbl"><thead><tr><th>${t('clinical.labels.variable')}</th><th>${t('clinical.labels.recorded')}</th><th>${t('clinical.labels.pct')}</th><th>${t('clinical.labels.missing')}</th></tr></thead><tbody>${body}</tbody></table>`;
}

// =================================================================== baseline characteristics by test status (+ SMD)
function smdCont(a,b){const p=Math.sqrt((sd(a)**2+sd(b)**2)/2);return p>0?Math.abs(mean(a)-mean(b))/p:NaN;}
function smdBin(pa,pb){const p=Math.sqrt((pa*(1-pa)+pb*(1-pb))/2);return p>0?Math.abs(pa-pb)/p:NaN;}
function drawBaseline(){
  const I=idx(), C=I.filter(i=>R.cc[i]===1), G=I.filter(i=>R.cc[i]===0);
  const bin=(arr,f)=>arr.filter(f).length;
  const ageC=C.filter(i=>R.age[i]!=null).map(i=>R.age[i]), ageG=G.filter(i=>R.age[i]!=null).map(i=>R.age[i]);
  const iqr=a=>a.length?`${quantile(a,.5).toFixed(0)} [${quantile(a,.25).toFixed(0)}–${quantile(a,.75).toFixed(0)}]`:'–';
  const propC={}, propG={};
  const rows=[['N', C.length, G.length, '']];
  rows.push(['Age, median [IQR] (yr)', iqr(ageC), iqr(ageG), isNaN(smdCont(ageC,ageG))?'':smdCont(ageC,ageG).toFixed(2)]);
  rows.push(['&nbsp;&nbsp;<span style="color:var(--muted)">missing age, n</span>', C.length-ageC.length, G.length-ageG.length, '']);
  const feat=[['Male sex', i=>R.sex[i]===1, i=>R.sex[i]!=null],
              ['Healthcare worker', i=>R.hcw[i]===1, ()=>true],
              ['Hospitalised', i=>R.hosp[i]===1, ()=>true],
              ['Died (recorded)', i=>diedOf(i), ()=>true],
              ['Symptom field recorded', i=>R.sym[i]!=null, ()=>true]];
  feat.forEach(([lab,f,ok])=>{
    const dc=C.filter(ok), dg=G.filter(ok);
    const pc=dc.length?bin(dc,f)/dc.length:NaN, pg=dg.length?bin(dg,f)/dg.length:NaN;
    rows.push([lab+', n (%)', `${bin(C,f)} (${(100*pc).toFixed(1)})`, `${bin(G,f)} (${(100*pg).toFixed(1)})`,
      isNaN(smdBin(pc,pg))?'':smdBin(pc,pg).toFixed(2)]);});
  const body=rows.map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td><td>${r[3]}</td></tr>`).join('');
  document.getElementById('baseline').innerHTML=
    `<table class="tbl"><thead><tr><th>${t('clinical.labels.characteristic')}</th><th>${t('clinical.labels.confirmed')} (N=${C.length})</th>`+
    `<th>${t('clinical.labels.test_negative')} (N=${G.length})</th><th>${t('clinical.labels.std_diff')}</th></tr></thead><tbody>${body}</tbody></table>`;
}

// =================================================================== daily epicurves
function stratSpec(){
  if(state.epiStrat==='sex') return {get:i=>R.sex[i]==null?null:(R.sex[i]?'male':'female'),order:['female','male'],col:c=>sexColor[c]};
  if(state.epiStrat==='ab')  return {get:i=>R.ab[i]==null?null:M.age_bands[R.ab[i]],order:M.age_bands,col:(c,j)=>abColor(M.age_bands.indexOf(c))};
  if(state.epiStrat==='hcw') return {get:i=>R.hcw[i]?'healthcare worker':'non-HCW',order:['non-HCW','healthcare worker'],col:c=>hcwColor[c]};
  return {get:i=>'all',order:['all'],col:_=>'#1c6bb0'};
}
function dailyStack(div,I,dateOf,title,ytitle){
  const rows=I.map(i=>[dateOf(i),i]).filter(r=>r[0]!=null);
  if(!rows.length){noData(div,280);document.getElementById(title).textContent='n=0';return;}
  const days=rows.map(r=>r[0]); let mn=Math.min(...days),mx=Math.max(...days);const n=mx-mn+1;
  const sp=stratSpec(); const cnt={}; sp.order.forEach(g=>cnt[g]=Array(n).fill(0));
  let tot=0;
  rows.forEach(([d,i])=>{const g=sp.get(i);if(g==null||!(g in cnt))return;cnt[g][d-mn]++;tot++;});
  const x=[...Array(n)].map((_,k)=>d2s(mn+k));
  const shown=sp.order.filter(g=>cnt[g].some(v=>v>0));
  const traces=shown.map((g,j)=>({type:'bar',name:g,x,y:cnt[g],
    marker:{color:sp.col(g,j)},hovertemplate:'%{x}<br>'+g+': %{y}<extra></extra>'}));
  // cumulative total (matches the stacked bars) on the secondary axis
  const cum=[]; let run=0;
  for(let k=0;k<n;k++){let dt=0;shown.forEach(g=>dt+=cnt[g][k]);run+=dt;cum.push(run);}
  traces.push({type:'scatter',mode:'lines',name:'cumulative',x,y:cum,yaxis:'y2',
    line:{color:'#16283d',width:2.5},hovertemplate:'%{x}<br>cumulative: %{y}<extra></extra>'});
  Plotly.react(div,traces,lay({height:290,barmode:'stack',bargap:0.05,
    legend:{orientation:'h',y:1.16,x:0,font:{size:10}},showlegend:true,
    xaxis:{type:'date',title:{text:'date',font:{size:11}}},
    yaxis:{title:{text:ytitle,font:{size:11}}},
    yaxis2:{title:{text:'cumulative',font:{size:11}},overlaying:'y',side:'right',
      rangemode:'tozero',gridcolor:'rgba(0,0,0,0)'},
    margin:{l:44,r:46,t:26,b:38}}),CFG);
  document.getElementById(title).textContent='n='+tot+' · cumulative '+run;
}
function drawEpi(){
  const I=idx();
  if(state.epiStrat==='hcw' && !hcwOk(I)){
    const msg=tf('clinical.sections.hcw_suppressed',{n:HCW_MIN_N});
    ['epi_adm','epi_death'].forEach(id=>{
      Plotly.react(id,[],lay({height:280,annotations:[{text:msg,showarrow:false,font:{color:'#8ea3b8',size:12},
        xref:'paper',yref:'paper',x:0.5,y:0.5,xanchor:'center',align:'center'}],
        xaxis:{visible:false},yaxis:{visible:false}}),CFG);
    });
    document.getElementById('cap_adm').textContent='';
    document.getElementById('cap_death').textContent='';
    return;
  }
  dailyStack('epi_adm', I.filter(i=>R.hs[i]!=null), i=>R.hs[i], 'cap_adm','admissions / day');
  dailyStack('epi_death', I.filter(i=>diedOf(i) && R.no[i]!=null), i=>R.no[i], 'cap_death','deaths / day');
}

// =================================================================== age-sex pyramid + positivity
function pyramid(div,I,filterFn,ttl){
  const sub=I.filter(filterFn);
  const nb=M.age_bands.length, f=Array(nb).fill(0), m=Array(nb).fill(0);
  sub.forEach(i=>{if(R.ab[i]==null||R.sex[i]==null)return;(R.sex[i]?m:f)[R.ab[i]]++;});
  if(!sub.length){noData(div,300);return;}
  const y=M.age_bands;
  const tf={type:'bar',orientation:'h',y,x:f.map(v=>-v),name:'female',marker:{color:sexColor.female},
    customdata:f,hovertemplate:'female %{y}: %{customdata}<extra></extra>'};
  const tm={type:'bar',orientation:'h',y,x:m,name:'male',marker:{color:sexColor.male},
    hovertemplate:'male %{y}: %{x}<extra></extra>'};
  const mx=Math.max(1,...f,...m);
  Plotly.react(div,[tf,tm],lay({height:300,barmode:'overlay',bargap:0.12,
    legend:{orientation:'h',y:1.13,x:0,font:{size:10}},
    xaxis:{title:{text:'← female    cases    male →',font:{size:11}},range:[-mx*1.05,mx*1.05],
      tickvals:[-mx,-Math.round(mx/2),0,Math.round(mx/2),mx],ticktext:[mx,Math.round(mx/2),0,Math.round(mx/2),mx]},
    yaxis:{categoryorder:'array',categoryarray:y},margin:{l:46,r:12,t:26,b:40}}),CFG);
}
function drawPyramid(){
  const I=idx();
  pyramid('pyr_pos', I, i=>R.cc[i]===1);
  pyramid('pyr_neg', I, i=>R.cc[i]===0);
  // positivity by age band x sex
  const nb=M.age_bands.length;
  const cf={0:Array(nb).fill(0),1:Array(nb).fill(0)}, tn={0:Array(nb).fill(0),1:Array(nb).fill(0)};
  I.forEach(i=>{if(R.ab[i]==null||R.sex[i]==null)return;const s=R.sex[i];
    if(R.cc[i]===1){cf[s][R.ab[i]]++;tn[s][R.ab[i]]++;}else if(R.cc[i]===0){tn[s][R.ab[i]]++;}});
  const traces=[0,1].map(s=>({type:'scatter',mode:'lines+markers',name:s?'male':'female',
    x:M.age_bands,y:cf[s].map((c,k)=>tn[s][k]?100*c/tn[s][k]:null),connectgaps:true,
    line:{color:s?sexColor.male:sexColor.female,width:2.5},marker:{size:6},
    customdata:cf[s].map((c,k)=>[c,tn[s][k]]),
    hovertemplate:(s?'male':'female')+' %{x}<br>positivity %{y:.0f}% (%{customdata[0]}/%{customdata[1]})<extra></extra>'}));
  Plotly.react('positivity',traces,lay({height:300,
    legend:{orientation:'h',y:1.13,x:0,font:{size:10}},
    xaxis:{title:{text:'age band (yr)',font:{size:11}}},
    yaxis:{title:{text:'test positivity %',font:{size:11}},range:[0,100]},margin:{l:46,r:12,t:26,b:40}}),CFG);
}

// =================================================================== mortality by admission week
function drawMortAdm(){
  const I=idx().filter(i=>R.hs[i]!=null);
  if(!I.length){noData('mortadm',300);document.getElementById('cap_mortadm').textContent='';return;}
  // weekly bins anchored to the first admission day (so the axis starts in early May,
  // not the epoch-based week boundary)
  const d0=Math.min(...I.map(i=>R.hs[i])), d1=Math.max(...I.map(i=>R.hs[i]));
  const n=Math.floor((d1-d0)/7)+1, wk=i=>Math.floor((R.hs[i]-d0)/7);
  const died=Array(n).fill(0),tot=Array(n).fill(0);
  I.forEach(i=>{const w=wk(i);tot[w]++;if(diedOf(i))died[w]++;});
  const x=[...Array(n)].map((_,k)=>d2s(d0+k*7));
  const MINADM=5;   // suppress the proportion line for weeks with too few admissions
  const prop=died.map((d,k)=>tot[k]>=MINADM?100*d/tot[k]:null);
  const ci=died.map((d,k)=>{if(tot[k]<MINADM)return[null,null];const[l,u]=wilson(d,tot[k]);return[100*l,100*u];});
  Plotly.react('mortadm',[
    {type:'bar',name:'admitted',x,y:tot,yaxis:'y2',marker:{color:'#cfe0ef'},
      hovertemplate:'%{x}<br>admitted: %{y}<extra></extra>'},
    {type:'scatter',mode:'lines+markers',name:'% died',x,y:prop,connectgaps:true,
      line:{color:'#c0392b',width:2.5},marker:{size:6},
      error_y:{type:'data',symmetric:false,array:ci.map((c,k)=>c[1]==null?null:c[1]-prop[k]),
        arrayminus:ci.map((c,k)=>c[0]==null?null:prop[k]-c[0]),color:'rgba(192,57,43,.35)',thickness:1,width:2},
      customdata:died.map((d,k)=>[d,tot[k]]),
      hovertemplate:'%{x}<br>died %{y:.0f}% (%{customdata[0]}/%{customdata[1]})<extra></extra>'}
  ],lay({height:320,legend:{orientation:'h',y:1.12,x:0,font:{size:10}},
    xaxis:{type:'date',title:{text:'week of admission',font:{size:11}}},
    yaxis:{title:{text:'% died (recorded)',font:{size:11}},range:[0,100]},
    yaxis2:{title:{text:'admitted',font:{size:11}},overlaying:'y',side:'right',gridcolor:'rgba(0,0,0,0)'},
    margin:{l:48,r:48,t:28,b:40}}),CFG);
  const td=I.filter(i=>diedOf(i)).length;
  document.getElementById('cap_mortadm').innerHTML=
    `<b>${td}</b> deaths among <b>${I.length}</b> admitted · overall <b>${(100*td/I.length).toFixed(1)}%</b> ·`+
    ` proportion (deaths recorded / admissions per week, Wilson 95% CI) shown only for weeks with ≥${MINADM} admissions`;
}

// =================================================================== Symptom Table 1 (confirmed vs negative)
function symCounts(I,statusFn,g){ // returns [x present, n total] for group g
  let x=0,n=0;I.forEach(i=>{if(R.sym[i]==null)return;if(statusFn(i)!==g)return;n++;});
  return n;
}
function renderSymTable(divId,capId,subsetFilter,cohortLabel){
  const IA=idx().filter(subsetFilter), I=IA.filter(i=>R.sym[i]!=null);
  const pos=I.filter(i=>R.cc[i]===1), neg=I.filter(i=>R.cc[i]===0);
  const N1=pos.length, N0=neg.length, both=N1&&N0;
  const totC=IA.filter(i=>R.cc[i]===1).length, totN=IA.filter(i=>R.cc[i]===0).length;
  const fmt=v=>v==null||isNaN(v)?'–':v.toFixed(2);
  const rows=SYM_ORDER.map(b=>{
    const c=SYMC[b];
    const x1=pos.filter(i=>hasSym(R.sym[i],b)).length, x0=neg.filter(i=>hasSym(R.sym[i],b)).length;
    return {lab:SYML[b],code:c,x1,x0,p1:N1?100*x1/N1:0,p0:N0?100*x0/N0:0,
      rd:newcombeRD(x1,N1,x0,N0),rr:katzRR(x1,N1,x0,N0)};
  });
  const body=rows.map(r=>{
    const rdpp=r.rd.map(v=>100*v);
    const rdcls=(both&&r.rd[1]>0)?'pos':((both&&r.rd[2]<0)?'neg':'');
    const rrcls=r.rr&&r.rr[1]>1?'pos':(r.rr&&r.rr[2]<1?'neg':'');
    const rdtxt=both?`${rdpp[0].toFixed(1)} (${rdpp[1].toFixed(1)} to ${rdpp[2].toFixed(1)})`:'–';
    return `<tr><td>${r.lab}${M.inferred.includes(r.code)?' *':''}</td>`+
      `<td>${r.x1} (${r.p1.toFixed(1)})</td><td>${r.x0} (${r.p0.toFixed(1)})</td>`+
      `<td class="${rdcls}">${rdtxt}</td>`+
      `<td class="${rrcls}">${r.rr?fmt(r.rr[0])+' ('+fmt(r.rr[1])+'–'+fmt(r.rr[2])+')':'–'}</td></tr>`;
  }).join('');
  document.getElementById(divId).innerHTML=
    `<table class="tbl"><thead><tr><th>Sign or symptom</th>`+
    `<th>Confirmed<br>(N=${N1})</th><th>Negative<br>(N=${N0})</th>`+
    `<th>Risk difference, pp<br>(95% CI)</th><th>Risk ratio<br>(95% CI)</th></tr></thead><tbody>${body}</tbody></table>`;
  document.getElementById(capId).innerHTML=
    `Cohort: <b>${cohortLabel}</b>. n (percent) among records with a completed symptom field `+
    `(<b>${N1}/${totC}</b> confirmed, <b>${N0}/${totN}</b> test-negative). Risk difference = confirmed − `+
    `negative (Newcombe 95% CI); risk ratio = Katz 95% CI (log scale). Ordered from least severe / most generic `+
    `to most severe / least generic. `+
    `<b>*</b> = inferred code. CI widths not adjusted for multiplicity; not for hypothesis testing.`;
}
function drawSymTable(){ renderSymTable('symtable','cap_symtable',()=>true,'all in scope'); }
function drawSymTableDied(){ renderSymTable('symtable_died','cap_symtable_died',i=>diedOf(i),'the deceased only'); }

// =================================================================== §5: confirmed prevalence + death RR (F06/F09)
function drawSymStatus(){
  const I=idx().filter(i=>R.cc[i]===1 && R.sym[i]!=null);
  if(I.length<10){noData('symstatus',26*NS+70);return;}
  const tot=I.length, cnt=Array(NS).fill(0);
  I.forEach(i=>{for(let b=0;b<NS;b++)if(hasSym(R.sym[i],b))cnt[b]++;});
  const order=SYM_ORDER;
  const y=order.map(b=>SYML[b]);
  const trace={type:'bar',orientation:'h',name:'confirmed (n='+tot+')',y,
    x:order.map(b=>100*cnt[b]/tot),marker:{color:statusColor.positive},opacity:.85,
    customdata:order.map(b=>cnt[b]),
    hovertemplate:'%{y}: %{x:.1f}% (%{customdata})<extra></extra>'};
  Plotly.react('symstatus',[trace],lay({height:26*NS+70,barmode:'group',bargap:0.25,showlegend:false,
    xaxis:{title:{text:'% with sign/symptom at presentation',font:{size:11}},range:[0,100]},
    yaxis:{categoryorder:'array',categoryarray:[...y].reverse(),automargin:true},
    margin:{l:8,r:12,t:10,b:38}}),CFG);
}
function drawDeathRR(){
  const I=idx().filter(i=>R.cc[i]===1 && R.sym[i]!=null);
  if(I.length<20){noData('deathrr',Math.max(420,22*NS+80));document.getElementById('cap_deathrr').textContent='';return;}
  const rows=SYM_ORDER.map(b=>{
    const withS=I.filter(i=>hasSym(R.sym[i],b));
    const without=I.filter(i=>!hasSym(R.sym[i],b));
    const d1=withS.filter(i=>diedOf(i)).length, n1=withS.length;
    const d0=without.filter(i=>diedOf(i)).length, n0=without.length;
    const rr=katzRR(d1,n1,d0,n0);
    return {lab:SYML[b],b,d1,n1,d0,n0,rr};
  }).filter(r=>r.n1>=10 && r.n0>=10 && r.rr);
  if(!rows.length){noData('deathrr',360);document.getElementById('cap_deathrr').textContent='';return;}
  const y=rows.map(r=>r.lab);
  const colors=rows.map(r=>r.rr[1]>1?'#c0392b':(r.rr[2]<1?'#178a6e':'#0f3c6b'));
  const trace={type:'scatter',mode:'markers',y,x:rows.map(r=>r.rr[0]),
    error_x:{type:'data',symmetric:false,
      array:rows.map(r=>r.rr[2]-r.rr[0]),arrayminus:rows.map(r=>r.rr[0]-r.rr[1]),
      color:'#5c7a99',thickness:1.5,width:0},
    marker:{color:colors,size:9,line:{color:'#fff',width:1}},
    customdata:rows.map(r=>[r.d1,r.n1,r.d0,r.n0,r.rr[1],r.rr[2]]),
    hovertemplate:'%{y}<br>RR %{x:.2f} (95% CI %{customdata[4]:.2f}–%{customdata[5]:.2f})'+
      '<br>with symptom: %{customdata[0]}/%{customdata[1]} died'+
      '<br>without: %{customdata[2]}/%{customdata[3]} died<extra></extra>'};
  const xmax=Math.max(2.5,...rows.map(r=>r.rr[2]*1.05));
  Plotly.react('deathrr',[trace],lay({height:Math.max(420,22*rows.length+80),showlegend:false,
    shapes:[{type:'line',x0:1,x1:1,y0:-0.5,y1:rows.length-0.5,
      line:{color:'#c0392b',width:1.5,dash:'dot'}}],
    xaxis:{title:{text:'relative risk of recorded death (with vs without symptom)',font:{size:11}},
      type:'log',range:[Math.log10(0.35),Math.log10(xmax)]},
    yaxis:{categoryorder:'array',categoryarray:[...y].reverse(),automargin:true},
    margin:{l:8,r:16,t:12,b:40}}),CFG);
  document.getElementById('cap_deathrr').innerHTML=
    `Confirmed cases with a symptom field (<b>${I.length}</b>). Crude Katz RR; red CI entirely &gt;1, green entirely &lt;1. `+
    `Symptoms with &lt;10 in either arm omitted. Exploratory — not multiplicity-adjusted.`;
}

// =================================================================== F11: symptoms × days-since-onset → death
function onsetDelayBin(d){
  if(d==null||d<0)return null;
  if(d<=2)return '0–2 d';
  if(d<=5)return '3–5 d';
  if(d<=9)return '6–9 d';
  return '≥10 d';
}
const ONSET_BINS=['0–2 d','3–5 d','6–9 d','≥10 d'];
function drawTriageRisk(){
  const I=idx().filter(i=>R.cc[i]===1 && R.sym[i]!=null && R.on[i]!=null && R.on[i]>=ONSET_MIN && R.hs[i]!=null);
  const MINC=5;
  if(I.length<20){noData('triage_risk',420);document.getElementById('cap_triage_risk').textContent='';return;}
  const order=SYM_ORDER;
  const z=order.map(b=>ONSET_BINS.map(bin=>{
    const sub=I.filter(i=>hasSym(R.sym[i],b) && onsetDelayBin(R.hs[i]-R.on[i])===bin);
    if(sub.length<MINC)return null;
    return 100*sub.filter(i=>diedOf(i)).length/sub.length;
  }));
  const labs=order.map(b=>SYML[b]);
  Plotly.react('triage_risk',[{type:'heatmap',z,x:ONSET_BINS,y:labs,zmin:0,zmax:60,zsmooth:false,
    xgap:1,ygap:1,colorscale:[[0,'#f3f7fa'],[0.5,'#f0c27a'],[1,'#c0392b']],
    hovertemplate:'%{y} · onset→admission %{x}<br>% died %{z:.0f}<extra></extra>',
    colorbar:{title:{text:'% died',side:'right'},thickness:11,len:.8}}],
    lay({height:Math.max(420,22*NS+100),
      xaxis:{title:{text:'days from symptom onset to hospital admission',font:{size:11}},type:'category'},
      yaxis:{autorange:'reversed',automargin:true,tickfont:{size:10},
        categoryorder:'array',categoryarray:labs},
      margin:{l:12,r:12,t:10,b:48}}),CFG);
  document.getElementById('cap_triage_risk').innerHTML=
    `Confirmed cases with usable onset (≥ 15 Jun) and admission date (<b>${I.length}</b>). `+
    `Cell = % with recorded death among those presenting with the row symptom in that delay bin; blank if n&lt;${MINC}. `+
    `Onset dates are self-reported — see §11 caveat.`;
}

// =================================================================== F13: aggregate HCW panel
function drawHcwAgg(){
  const root=document.getElementById('hcw_agg');
  const cap=document.getElementById('cap_hcw_agg');
  if(!root)return;
  const I=idx(), H=I.filter(i=>R.hcw[i]===1);
  if(!hcwOk(I)){
    root.innerHTML=`<p class="cap">${tf('clinical.sections.hcw_suppressed',{n:HCW_MIN_N})}</p>`;
    if(cap)cap.textContent='';
    return;
  }
  const n=H.length;
  const died=H.filter(i=>diedOf(i)).length;
  const conf=H.filter(i=>R.cc[i]===1).length;
  const female=H.filter(i=>R.sex[i]===0).length;
  const male=H.filter(i=>R.sex[i]===1).length;
  const ages=H.filter(i=>R.age[i]!=null).map(i=>R.age[i]);
  const medAge=ages.length?quantile(ages,.5):null;
  const withSym=H.filter(i=>R.sym[i]!=null);
  const freq=SYM_ORDER.map(b=>{
    const x=withSym.filter(i=>hasSym(R.sym[i],b)).length;
    return {lab:SYML[b],x,p:withSym.length?100*x/withSym.length:0};
  }).filter(r=>r.x>0).sort((a,b)=>b.p-a.p).slice(0,8);
  root.innerHTML=
    `<div class="kpis" style="grid-template-columns:repeat(4,1fr);margin-bottom:12px">`+
    `<div class="kpi"><div class="v">${n}</div><div class="k">HCW in selection</div><div class="s">${(100*n/Math.max(I.length,1)).toFixed(1)}% of scope</div></div>`+
    `<div class="kpi"><div class="v">${conf}</div><div class="k">confirmed</div><div class="s">${n?((100*conf/n).toFixed(0)+'% of HCW'):''}</div></div>`+
    `<div class="kpi"><div class="v">${died}</div><div class="k">deaths recorded</div><div class="s">${n?((100*died/n).toFixed(0)+'% of HCW'):''}</div></div>`+
    `<div class="kpi"><div class="v">${medAge==null?'–':medAge.toFixed(0)}</div><div class="k">median age (yr)</div><div class="s">${female} F · ${male} M</div></div>`+
    `</div>`+
    `<table class="tbl"><thead><tr><th>Most frequent presenting symptoms (HCW with symptom field)</th><th>n</th><th>%</th></tr></thead>`+
    `<tbody>${freq.map(r=>`<tr><td>${r.lab}</td><td>${r.x}</td><td>${r.p.toFixed(1)}</td></tr>`).join('')}</tbody></table>`;
  if(cap)cap.innerHTML=`Aggregated only — no onset dates or daily timelines. Symptom % among <b>${withSym.length}</b> HCW with a symptom field.`;
}

// =================================================================== symptom correlation heatmap
function drawCorr(){
  const I=coCohort(idx().filter(i=>R.sym[i]!=null));
  // Size so matrix cells stay roughly square in the half-width panel.
  const host=document.getElementById('corr');
  const avail=Math.max(280,(host&&host.clientWidth)||480);
  const cell=Math.max(12,Math.floor((avail-150)/NS));
  const corrH=Math.max(340,cell*NS+110);
  if(I.length<10){noData('corr',corrH);return;}
  const p=Array(NS).fill(0), pab=Array.from({length:NS},()=>Array(NS).fill(0));
  I.forEach(i=>{for(let a=0;a<NS;a++){const ha=hasSym(R.sym[i],a);if(ha){p[a]++;for(let b=0;b<NS;b++)if(hasSym(R.sym[i],b))pab[a][b]++;}}});
  const n=I.length, order=SYM_ORDER;
  const z=order.map(a=>order.map(b=>{
    if(a===b)return null;
    const pa=p[a]/n, pb=p[b]/n, pj=pab[a][b]/n;
    const den=Math.sqrt(pa*(1-pa)*pb*(1-pb));return den>0?(pj-pa*pb)/den:0;}));
  // One discrete symptom per row/column; axes follow severity order.
  const labs=order.map(b=>SYML[b]);
  const axisCats={type:'category',categoryorder:'array',categoryarray:labs,
    tickmode:'array',tickvals:labs,ticktext:labs,tickfont:{size:9},automargin:true};
  Plotly.react('corr',[{type:'heatmap',z,x:labs,y:labs,zmin:-.5,zmax:.5,zsmooth:false,
    xgap:1,ygap:1,
    colorscale:[[0,'#178a6e'],[0.5,'#f3f7fa'],[1,'#c0392b']],
    hovertemplate:'%{y} × %{x}<br>φ = %{z:.2f}<extra></extra>',
    colorbar:{title:{text:'φ',side:'right'},thickness:11,len:.8}}],
    lay({height:corrH,
      xaxis:Object.assign({},axisCats,{tickangle:-55,constrain:'domain'}),
      yaxis:Object.assign({},axisCats,{autorange:'reversed',scaleanchor:'x',scaleratio:1,constrain:'domain'}),
      margin:{l:12,r:12,t:8,b:8}}),CFG);
}

// =================================================================== UpSet: combinations of top-6 symptoms
function drawUpset(){
  const I=coCohort(idx().filter(i=>R.sym[i]!=null));
  if(I.length<10){noData('upset',420);document.getElementById('cap_upset').textContent='';return;}
  const freq=Array(NS).fill(0);I.forEach(i=>{for(let b=0;b<NS;b++)if(hasSym(R.sym[i],b))freq[b]++;});
  // Six most frequent symptoms, row order by severity (least → most).
  const top=[...Array(NS).keys()].sort((a,b)=>freq[b]-freq[a]).slice(0,6)
    .sort((a,b)=>SYM_ORDER.indexOf(a)-SYM_ORDER.indexOf(b));
  const combos={};
  I.forEach(i=>{let key=0;top.forEach((b,k)=>{if(hasSym(R.sym[i],b))key|=(1<<k);});combos[key]=(combos[key]||0)+1;});
  let arr=Object.entries(combos).map(([k,v])=>[+k,v]).sort((a,b)=>b[1]-a[1]).slice(0,12);
  const nc=arr.length, tot=I.length;
  const xIdx=[...Array(nc).keys()];
  const bar={type:'bar',x:xIdx,y:arr.map(a=>a[1]),marker:{color:'#c0392b'},
    text:arr.map(a=>`${a[1]}<br>${(100*a[1]/tot).toFixed(0)}%`),textposition:'outside',textfont:{size:9},
    hovertemplate:'%{y} patients (%{text})<extra></extra>',xaxis:'x',yaxis:'y'};
  // matrix dots (6 rows; row 0 at bottom). present=dark, absent=light
  const gx=[],gy=[],dx=[],dy=[],lx=[],ly=[];
  arr.forEach(([key,_],c)=>{const present=[];top.forEach((b,k)=>{if((key>>k)&1)present.push(k);
      (((key>>k)&1)?(function(){dx.push(c);dy.push(k);})():(function(){gx.push(c);gy.push(k);})());});
    if(present.length){lx.push(c,c,null);ly.push(Math.min(...present),Math.max(...present),null);}});
  const grey={type:'scatter',mode:'markers',x:gx,y:gy,marker:{color:'#d3dde7',size:11},hoverinfo:'skip',xaxis:'x',yaxis:'y2'};
  const line={type:'scatter',mode:'lines',x:lx,y:ly,line:{color:'#0f3c6b',width:2},hoverinfo:'skip',xaxis:'x',yaxis:'y2'};
  const dark={type:'scatter',mode:'markers',x:dx,y:dy,marker:{color:'#0f3c6b',size:11},hoverinfo:'skip',xaxis:'x',yaxis:'y2'};
  const ytick=top.map((b,k)=>`${SYML[b]} (${(100*freq[b]/tot).toFixed(0)}%)`);
  const covered=arr.reduce((s,a)=>s+a[1],0);
  Plotly.react('upset',[bar,grey,line,dark],lay({height:430,showlegend:false,
    xaxis:{domain:[0,1],anchor:'y2',range:[-0.6,nc-0.4],showticklabels:false,zeroline:false,showgrid:false},
    yaxis:{domain:[0.42,1],title:{text:'patients with combination',font:{size:11}},zeroline:false},
    yaxis2:{domain:[0,0.36],anchor:'x',range:[-0.6,5.6],tickvals:top.map((_,k)=>k),ticktext:ytick,
      autorange:false,showgrid:false,zeroline:false,tickfont:{size:10.5}},
    margin:{l:150,r:12,t:16,b:8}}),CFG);
  const cohL=state.symCohort==='confirmed'?'confirmed cases':'all with a symptom field';
  document.getElementById('cap_upset').innerHTML=
    `Cohort: <b>${cohL}</b>. Combinations over the six most frequent symptoms `+
    `(<b>${top.map(b=>SYML[b]).join(', ')}</b>); other symptoms disregarded. Top ${nc} combinations shown, `+
    `covering <b>${covered}</b> of ${tot} patients (${(100*covered/tot).toFixed(0)}%). Left % = overall frequency. `+
    `Mirrors Fig. S2 of the appendix.`;
}

// =================================================================== Ct by outcome (per assay)
// Restricted to ANTE-MORTEM BLOOD: deceased-at-collection samples are almost all
// post-mortem swabs (different specimen, degraded RNA) — pooling confounds outcome
// with specimen type. "Died" here = death alert among ante-mortem-sampled patients.
function ctBox(div,I,ctKey,capId,assay){
  const rows=I.map(i=>[R[ctKey][i],i]).filter(r=>r[0]!=null);
  if(rows.length<5){noData(div,300);document.getElementById(capId).textContent=
    'Too few ante-mortem blood '+assay+' Ct values in this selection.';return;}
  const grp={died:[],nod:[]};
  rows.forEach(([v,i])=>{(R.alert[i]===1?grp.died:grp.nod).push(v);});
  const traces=[
    {type:'box',name:'no death rec. (n='+grp.nod.length+')',y:grp.nod,marker:{color:'#5c7a99'},
      boxpoints:'all',jitter:.4,pointpos:0,marker_size:3,fillcolor:'rgba(92,122,153,.25)',
      hovertemplate:'Ct %{y}<extra></extra>'},
    {type:'box',name:'died (n='+grp.died.length+')',y:grp.died,marker:{color:'#c0392b'},
      boxpoints:'all',jitter:.4,pointpos:0,marker_size:3,fillcolor:'rgba(192,57,43,.25)',
      hovertemplate:'Ct %{y}<extra></extra>'}];
  Plotly.react(div,traces,lay({height:320,showlegend:false,
    yaxis:{title:{text:assay+' Ct (lower = higher viral load)',font:{size:11}},autorange:'reversed'},
    xaxis:{},margin:{l:52,r:12,t:12,b:30}}),CFG);
  const md=(grp.died.length&&grp.nod.length)?mean(grp.died)-mean(grp.nod):NaN;
  const q=a=>`${quantile(a,.5).toFixed(1)} [${quantile(a,.25).toFixed(1)}–${quantile(a,.75).toFixed(1)}]`;
  document.getElementById(capId).innerHTML=
    `Ante-mortem blood only. Median Ct — died <b>${grp.died.length?q(grp.died):'–'}</b> `+
    `vs no death <b>${grp.nod.length?q(grp.nod):'–'}</b> · crude mean Δ `+
    `<b>${isNaN(md)?'–':(md>=0?'+':'')+md.toFixed(1)}</b> (n=${grp.died.length} died). `+
    `Died = death-alert among ante-mortem-sampled patients; small n, interpret cautiously.`;
}
function drawCt(){
  // positives, ante-mortem (alive at collection), blood specimen — removes the
  // specimen / post-mortem confound; see note in §7. Altona (PCRA) only.
  const I=idx().filter(i=>R.cc[i]===1 && R.sdec[i]===0 && R.st[i]===BLOOD);
  ctBox('ct_altona',  I, 'ctA','cap_ctA','Altona (PCRA)');
}

// =================================================================== delays (empirical + fits)
function fitStratList(key){const w=FITS[key]&&FITS[key][state.win]?FITS[key][state.win]:{};return Object.keys(w);}
function drawOneDelay(key,div,capId,stratSelId){
  const I=idx();
  const vals=[];I.forEach(i=>{const d=delayVal(i,key);if(d!=null)vals.push(d);});
  const sp=DACC[key], xhi=sp.win[1]===90?45:(sp.win[1]===60?30:sp.win[1]);
  const traces=[{type:'histogram',x:vals,histnorm:'probability',xbins:{start:-0.5,size:1,end:sp.win[1]+0.5},
    marker:{color:'#9fb0c0'},opacity:.6,name:'empirical (selection)',
    hovertemplate:'%{x} d: %{y:.3f}<extra></extra>'}];
  const sk=document.getElementById(stratSelId)?document.getElementById(stratSelId).value:'overall';
  const entry=(FITS[key]&&FITS[key][state.win])?FITS[key][state.win][sk]:null;
  const isEp=!!(entry&&entry.method&&entry.method.indexOf('epidist')===0);
  const cri=c=>(Array.isArray(c)&&c.length===2)?` <span style="color:var(--muted)">(${c[0].toFixed(1)}–${c[1].toFixed(1)})</span>`:'';
  let icType='',minIC=Infinity, rows='';
  if(entry&&entry.families&&Object.keys(entry.families).length){
    const fl=Object.values(entry.families);icType=(fl.find(f=>f.ic_type)||{}).ic_type||'';
    fl.forEach(f=>{if(f.ic!=null&&f.ic<minIC)minIC=f.ic;});
    Object.entries(entry.families).forEach(([fam,f])=>{
      traces.push({type:'scatter',mode:'lines',x:f.curve.x,y:f.curve.y,
        line:{color:famcol[fam],width:fam===entry.best?3:1.6,dash:fam===entry.best?'solid':'dot'},
        name:fam+(fam===entry.best?' ★':''),hovertemplate:fam+' P(%{x} d)=%{y:.3f}<extra></extra>'});
      const dic=(f.ic!=null&&isFinite(minIC))?(f.ic-minIC).toFixed(1):'–';
      rows+=`<tr><td>${fam}${fam===entry.best?' ★':''}</td><td>${f.median.toFixed(1)}${cri(f.median_cri)}</td>`+
        `<td>${f.mean.toFixed(1)}${cri(f.mean_cri)}</td><td>${f.p90.toFixed(1)}</td>`+
        `<td>${f.ic!=null?f.ic.toFixed(1):'–'}</td><td>${dic}</td></tr>`;});
  }
  Plotly.react(div,traces,lay({height:250,showlegend:true,barmode:'overlay',
    legend:{orientation:'h',y:1.16,x:0,font:{size:9.5}},
    xaxis:{title:{text:'days',font:{size:11}},range:[-0.5,xhi]},
    yaxis:{title:{text:'proportion',font:{size:11}}},margin:{l:46,r:10,t:24,b:36}}),CFG);
  const meth=entry?entry.method:'—', nn=entry?entry.n:0, bf=entry&&entry.best?entry.families[entry.best]:null;
  const iv=isEp?' (95% CrI)':'';
  let diag='';
  if(isEp&&bf&&bf.rhat!=null){const ok=bf.rhat<=1.05&&(bf.ndiv==null||bf.ndiv===0);
    diag=` · <span style="color:${ok?'var(--accent2)':'var(--bad)'}">convergence R̂=${bf.rhat}`+
      (bf.ess!=null?`, ESS≥${bf.ess}`:'')+`, ${bf.ndiv==null?'?':bf.ndiv} divergent</span>`;}
  document.getElementById(capId).innerHTML=
    `selection (empirical): n=<b>${vals.length}</b>, median <b>${vals.length?quantile(vals,.5).toFixed(1):'–'} d</b>, `+
    `mean ${vals.length?mean(vals).toFixed(1):'–'} d · &nbsp;model [<b>${sk}</b>, ${meth}, n=${nn}]`+diag+
    (rows?` best <span class="fitbadge">${entry.best} ★</span>`+
      `<table class="tbl" style="width:auto;margin-top:5px"><thead><tr><th>family</th><th>median${iv}</th><th>mean${iv}</th>`+
      `<th>90th</th><th>${icType}↓</th><th>Δ</th></tr></thead><tbody>${rows}</tbody></table>`
      :' · <i>parametric fit not available (n too small for a stable fit); empirical distribution only</i>');
}
function buildStratSel(id,key){const s=document.getElementById(id);const keys=fitStratList(key);
  const cur=s.value;s.innerHTML=keys.map(k=>`<option value="${k}">${k}</option>`).join('');
  if(keys.includes(cur))s.value=cur;else s.value='overall';}
function drawDelays(){
  ['onset_to_admission','admission_to_exit','onset_to_death'].forEach(k=>buildStratSel('strat_'+k,k));
  drawOneDelay('onset_to_admission','d_adm','cap_d_adm','strat_onset_to_admission');
  drawOneDelay('admission_to_exit','d_exit','cap_d_exit','strat_admission_to_exit');
  drawOneDelay('onset_to_death','d_death','cap_d_death','strat_onset_to_death');
}

// =================================================================== admission delay vs onset symptoms
function drawAdmSym(){
  const I=idx();
  const wd=I.map(i=>[delayVal(i,'onset_to_admission'),i]).filter(r=>r[0]!=null);
  if(wd.length<10){noData('admsym',360);document.getElementById('cap_admsym').textContent='';return;}
  const allv=wd.map(r=>r[0]), overall=quantile(allv,.5), oq1=quantile(allv,.25), oq3=quantile(allv,.75);
  const rows=SYM_ORDER.map(b=>{
    const v=wd.filter(([_,i])=>hasSym(R.sym[i],b)).map(r=>r[0]);
    return {lab:SYML[b], n:v.length, med:v.length?quantile(v,.5):null,
            q1:v.length?quantile(v,.25):null, q3:v.length?quantile(v,.75):null};
  }).filter(r=>r.n>=20);
  if(!rows.length){noData('admsym',360);document.getElementById('cap_admsym').textContent='too few symptom-positive records';return;}
  const y=rows.map(r=>r.lab);
  // forest-style: median marker + interquartile-range line per presenting symptom
  const trace={type:'scatter',mode:'markers',y,x:rows.map(r=>r.med),name:'median (IQR)',
    error_x:{type:'data',symmetric:false,array:rows.map(r=>r.q3-r.med),arrayminus:rows.map(r=>r.med-r.q1),
      color:'#1c6bb0',thickness:3,width:0},
    marker:{color:'#0f3c6b',size:9,line:{color:'#fff',width:1}},
    customdata:rows.map(r=>[r.n,r.q1,r.q3]),
    hovertemplate:'%{y}<br>median %{x:.1f} d · IQR %{customdata[1]:.1f}–%{customdata[2]:.1f} d · n=%{customdata[0]}<extra></extra>'};
  Plotly.react('admsym',[trace],lay({height:27*rows.length+80,showlegend:false,
    shapes:[
      {type:'rect',x0:oq1,x1:oq3,y0:-0.5,y1:rows.length-0.5,fillcolor:'rgba(95,116,136,.10)',line:{width:0},layer:'below'},
      {type:'line',x0:overall,x1:overall,y0:-0.5,y1:rows.length-0.5,line:{color:'#c0392b',width:1.5,dash:'dot'}}],
    annotations:[{x:overall,y:rows.length-0.5,yanchor:'bottom',xanchor:'left',showarrow:false,
      text:'overall median '+overall.toFixed(1)+' d (shaded = overall IQR)',font:{size:10,color:'#c0392b'}}],
    xaxis:{title:{text:'onset → hospital admission delay, days (median ● with interquartile range)',font:{size:11}},rangemode:'tozero'},
    yaxis:{categoryorder:'array',categoryarray:[...y].reverse(),automargin:true},margin:{l:8,r:16,t:22,b:40}}),CFG);
  document.getElementById('cap_admsym').innerHTML=
    `For cases <b>presenting with</b> each onset symptom: the <b>median</b> onset→admission delay (●) and its `+
    `<b>interquartile range</b> (line, middle 50% of patients). Red dotted line = overall median `+
    `<b>${overall.toFixed(1)} d</b>; grey band = overall IQR. Symptoms whose marker sits right of the line tend `+
    `to present/admit later. Onset ≥ 15 Jun; symptoms with ≥20 records, ordered least→most severe. Descriptive.`;
}

// =================================================================== adjusted RR table
function drawAdjRR(){
  const rows=(ADJ[state.win]||[]).slice().sort((a,b)=>symRank(a.code)-symRank(b.code));
  const fmt=t=>t?`${t[0].toFixed(2)} (${t[1].toFixed(2)}–${t[2].toFixed(2)})`:'<i>NE</i>';
  const cls=t=>t?(t[1]>1?'pos':(t[2]<1?'neg':'')):'';
  const body=rows.map(r=>{
    const lab=(function(){const i=SYMC.indexOf(r.code);return i>=0?SYML[i]:r.label;})();
    return `<tr><td>${lab}${M.inferred.includes(r.code)?' *':''}</td>`+
    `<td>${r.n}/${r.tot}</td><td class="${cls(r.male)}">${fmt(r.male)}</td>`+
    `<td class="${cls(r.age)}">${fmt(r.age)}</td></tr>`;
  }).join('');
  document.getElementById('adjrr').innerHTML= rows.length?
    `<table class="tbl"><thead><tr><th>Sign or symptom</th><th>events/total</th>`+
    `<th>aRR male sex (95% CI)</th><th>aRR per 10-yr age (95% CI)</th></tr></thead><tbody>${body}</tbody></table>`
    :'<p class="cap">Not enough confirmed cases with recorded sex, age &amp; symptoms in this window.</p>';
}

// =================================================================== onset documentation: included vs excluded
function drawOnsetSel(){
  const I=idx().filter(i=>R.cc[i]===1);
  const inc=I.filter(i=>R.on[i]!=null && R.on[i]>=ONSET_MIN);
  const exc=I.filter(i=>!(R.on[i]!=null && R.on[i]>=ONSET_MIN));
  const bin=(arr,f)=>arr.filter(f).length;
  const ageI=inc.filter(i=>R.age[i]!=null).map(i=>R.age[i]), ageE=exc.filter(i=>R.age[i]!=null).map(i=>R.age[i]);
  const iqr=a=>a.length?`${quantile(a,.5).toFixed(0)} [${quantile(a,.25).toFixed(0)}–${quantile(a,.75).toFixed(0)}]`:'–';
  const rows=[['N', inc.length, exc.length, '']];
  rows.push(['Age, median [IQR] (yr)', iqr(ageI), iqr(ageE), isNaN(smdCont(ageI,ageE))?'':smdCont(ageI,ageE).toFixed(2)]);
  const feat=[['Male sex', i=>R.sex[i]===1, i=>R.sex[i]!=null],
              ['Died (recorded)', i=>diedOf(i), ()=>true],
              ['Hospitalised', i=>R.hosp[i]===1, ()=>true],
              ['Ct available (any assay)', i=>R.ctR[i]!=null||R.ctA[i]!=null, ()=>true]];
  feat.forEach(([lab,f,ok])=>{const di=inc.filter(ok), de=exc.filter(ok);
    const pi=di.length?bin(di,f)/di.length:NaN, pe=de.length?bin(de,f)/de.length:NaN;
    rows.push([lab+', n (%)', `${bin(inc,f)} (${(100*pi).toFixed(1)})`, `${bin(exc,f)} (${(100*pe).toFixed(1)})`,
      isNaN(smdBin(pi,pe))?'':smdBin(pi,pe).toFixed(2)]);});
  document.getElementById('onsetsel').innerHTML=
    `<table class="tbl"><thead><tr><th>Characteristic (confirmed cases)</th>`+
    `<th>Included · onset ≥ 15 Jun (N=${inc.length})</th><th>Excluded (N=${exc.length})</th>`+
    `<th>Std. diff.</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td><td>${r[3]}</td></tr>`).join('')}</tbody></table>`;
  const miss=exc.filter(i=>R.on[i]==null).length, early=exc.length-miss;
  document.getElementById('cap_onsetsel').innerHTML=
    `Onset-based analyses (delays §8–10) require symptom onset ≥ 15 Jun 2026 and are `+
    `<b>complete-case</b>. Of ${I.length} confirmed cases in the selection, <b>${inc.length}</b> `+
    `(${(100*inc.length/Math.max(I.length,1)).toFixed(0)}%) qualify; ${exc.length} are excluded `+
    `(${miss} onset missing, ${early} onset before 15 Jun). Sizeable standardized differences would signal `+
    `selection bias in those analyses.`;
}

// =================================================================== figure export (JPG / PDF)
function figMeta(panel){
  let title='';const pt=panel.querySelector('.ptitle');
  if(pt){const c=pt.cloneNode(true);c.querySelectorAll('span,select,label').forEach(e=>e.remove());title=c.textContent.trim();}
  const sec=panel.closest('section'), h=sec?sec.querySelector('.sfxhead h2'):null;
  const secTitle=h?h.textContent.trim():'';
  if(!title)title=secTitle||'Figure';
  const cap=panel.querySelector('.cap');
  return {title, section:secTitle, caption:cap?cap.innerText.trim():''};
}
function dlData(dataUrl,fname){const a=document.createElement('a');a.href=dataUrl;a.download=fname;
  document.body.appendChild(a);a.click();a.remove();}
async function exportFigure(divId,fmt,btn){
  const gd=document.getElementById(divId);if(!gd)return;
  const panel=gd.closest('.panel'), meta=figMeta(panel);
  if(btn)btn.disabled=true;
  try{
    const S=2, W=Math.max(gd.offsetWidth||760,320), H=Math.max(gd.offsetHeight||360,240);
    const url=await Plotly.toImage(gd,{format:'png',width:W,height:H,scale:S});
    const img=new Image();await new Promise((res,rej)=>{img.onload=res;img.onerror=rej;img.src=url;});
    const cv=document.createElement('canvas'), cx=cv.getContext('2d');
    const pad=20*S, cw=W*S+pad*2, maxw=W*S;
    const F=px=>`${px*S}px -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif`;
    const wrap=(text,font)=>{cx.font=font;const ws=text.split(/\s+/),ls=[];let cur='';
      ws.forEach(w=>{const t=cur?cur+' '+w:w;if(cx.measureText(t).width>maxw&&cur){ls.push(cur);cur=w;}else cur=t;});
      if(cur)ls.push(cur);return ls;};
    const dash='BVD clinical characteristics — DR Congo';
    const now=new Date().toISOString().slice(0,10);
    const capLines=meta.caption?wrap(meta.caption,F(11)):[];
    const ack1='Source: INRB BDBV 2026 Epidemic Dashboard — https://inrb-umie.github.io/BDBV2026-Epidemic_Dashboard/';
    const ack2=`Data cut ${M.snapshot} · exported ${now} · analytic scope ${M.n_scope.toLocaleString()} of ${M.n_raw.toLocaleString()} records · exploratory, 95% CI/CrI not adjusted for multiplicity.`;
    const ackLines=wrap(ack1,F(10.5)).concat(wrap(ack2,F(10.5)));
    const lhT=21*S, lhS=18*S, lhC=15*S, lhA=14.5*S;
    const headerH=pad+lhT+lhS+6*S, chartH=H*S;
    const footerH=(capLines.length?capLines.length*lhC+10*S:6*S)+ackLines.length*lhA+pad;
    cv.width=cw; cv.height=headerH+chartH+footerH;
    cx.fillStyle='#ffffff';cx.fillRect(0,0,cv.width,cv.height);cx.textBaseline='top';
    cx.fillStyle='#0f3c6b';cx.font='700 '+F(15);cx.fillText(dash,pad,pad);
    cx.fillStyle='#16283d';cx.font='600 '+F(12.5);
    cx.fillText((meta.section&&meta.section!==meta.title?meta.section+' — ':'')+meta.title,pad,pad+lhT);
    if(LOGOIMG.complete && LOGOIMG.naturalWidth){const lh=34*S, lw=lh*LOGOIMG.naturalWidth/LOGOIMG.naturalHeight;
      try{cx.drawImage(LOGOIMG, cw-pad-lw, pad, lw, lh);}catch(e){}}
    cx.drawImage(img,pad,headerH,W*S,chartH);
    let y=headerH+chartH+6*S;
    cx.strokeStyle='#d8e2ec';cx.lineWidth=S;cx.beginPath();cx.moveTo(pad,y);cx.lineTo(cw-pad,y);cx.stroke();y+=9*S;
    cx.fillStyle='#5f7488';cx.font=F(11);capLines.forEach(l=>{cx.fillText(l,pad,y);y+=lhC;});
    if(capLines.length)y+=5*S;
    cx.fillStyle='#0f3c6b';cx.font='italic '+F(10.5);ackLines.forEach(l=>{cx.fillText(l,pad,y);y+=lhA;});
    const base=('BVD_'+meta.title).replace(/[^A-Za-z0-9]+/g,'_').replace(/^_+|_+$/g,'').slice(0,60);
    if(fmt==='jpg'){dlData(cv.toDataURL('image/jpeg',0.95),base+'.jpg');}
    else{const {jsPDF}=window.jspdf, pw=cv.width/S, ph=cv.height/S;
      const pdf=new jsPDF({orientation:pw>=ph?'l':'p',unit:'pt',format:[pw,ph]});
      pdf.addImage(cv.toDataURL('image/jpeg',0.96),'JPEG',0,0,pw,ph);pdf.save(base+'.pdf');}
  }catch(e){console.error('figure export failed',e);}
  if(btn)btn.disabled=false;
}
function addFigButtons(){
  document.querySelectorAll('.panel').forEach(panel=>{
    if(panel.querySelector('.figdl'))return;
    const chart=panel.querySelector('.chart[id]');if(!chart)return;
    const ctl=document.createElement('div');ctl.className='figdl';
    ctl.innerHTML='<button data-f="jpg" title="Download JPG (with caption + source)">JPG</button>'+
                  '<button data-f="pdf" title="Download PDF (with caption + source)">PDF</button>';
    ctl.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>exportFigure(chart.id,b.dataset.f,b)));
    panel.appendChild(ctl);
  });
}

// =================================================================== controls / init
function renderAll(){
  document.getElementById('nrec').innerHTML='<b>'+idx().length.toLocaleString()+'</b> records';
  drawKPIs();drawCompleteness();drawBaseline();drawHcwAgg();drawEpi();drawPyramid();drawMortAdm();drawSymTable();
  drawSymTableDied();drawSymStatus();drawDeathRR();drawTriageRisk();drawCorr();drawUpset();drawCt();drawOnsetSel();drawDelays();drawAdmSym();drawAdjRR();
}
function buildMulti(id,items){document.getElementById(id).innerHTML=
  items.map((t,i)=>`<option value="${i}">${t}</option>`).join('');}
function onFilter(){
  state.prov=new Set(selVals('f_prov'));state.ageb=new Set(selVals('f_age'));renderAll();}
function segWire(role,key,fn){document.querySelectorAll(`.seg[data-role=${role}] button`).forEach(b=>
  b.addEventListener('click',()=>{document.querySelectorAll(`.seg[data-role=${role}] button`).forEach(x=>x.classList.remove('on'));
    b.classList.add('on');state[key]=b.dataset.v;(fn||renderAll)();}));}
function init(){
  buildMulti('f_prov',M.provinces);buildMulti('f_age',M.age_bands);
  document.getElementById('f_prov').addEventListener('change',onFilter);
  document.getElementById('f_age').addEventListener('change',onFilter);
  segWire('win','win');segWire('sex','sex');segWire('hcw','hcw');
  segWire('epistrat','epiStrat',drawEpi);
  segWire('symcohort','symCohort',()=>{drawCorr();drawUpset();});
  document.getElementById('f_vital').addEventListener('change',e=>{state.vital=e.target.value;renderAll();});
  document.getElementById('reset').addEventListener('click',()=>{
    ['f_prov','f_age'].forEach(id=>[...document.getElementById(id).options].forEach(o=>o.selected=false));
    state.prov.clear();state.ageb.clear();state.sex='all';state.hcw='all';state.win='all';state.vital='union';
    document.getElementById('f_vital').value='union';
    ['win','sex','hcw'].forEach(r=>document.querySelectorAll(`.seg[data-role=${r}] button`).forEach(x=>
      x.classList.toggle('on',x.dataset.v==='all')));
    applyClinicalStaticI18n(); renderAll();});
  ['onset_to_admission','admission_to_exit','onset_to_death'].forEach(k=>{
    const el=document.getElementById('strat_'+k);if(el)el.addEventListener('change',drawDelays);});
  wireChrome();
  applyClinicalStaticI18n();
  renderAll();
  addFigButtons();
}
window.addEventListener('error',e=>{const b=document.getElementById('errbar');
  b.style.display='block';b.textContent='JS error: '+e.message+' @'+(e.lineno||'?');});
init();
"""

HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BVD clinical dashboard — DRC</title>
<link rel="stylesheet" href="__ASSETS_PREFIX__dashboard.css" />
<style>__CSS__
/* --- clinical page layout inside Epidemic Dashboard chrome --- */
body.clinical-page{margin:0;background:#0b0f14;color:#e8e8e8;height:100vh;
  display:flex;flex-direction:column;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
body.clinical-page #site-header{position:relative;flex:0 0 auto;}
body.clinical-page #page-tabs{position:relative;z-index:40;flex:0 0 auto;}
body.clinical-page .clinical-scroll{overflow:hidden;flex:1 1 auto;min-height:0;
  display:flex;flex-direction:column;
  background:var(--bg,#eef3f7);color:var(--ink,#16283d);}
body.clinical-page .clinical-scroll > .clinical-title-block,
body.clinical-page .clinical-scroll > .filterbar,
body.clinical-page .clinical-scroll > #errbar{flex:0 0 auto;}
body.clinical-page .clinical-scroll header{position:relative;}
body.clinical-page .filterbar{position:relative;top:auto;z-index:30;}
body.clinical-page .clinical-body{flex:1 1 auto;min-height:0;overflow:auto;}
body.clinical-page #view-switcher{position:relative;left:auto;right:auto;bottom:auto;
  flex:0 0 auto;width:100%;}
body.clinical-page .modal{z-index:2000;}
body.clinical-page .modal .sheet{background:#1a1a1a;color:#eee;max-width:820px;
  margin:5vh auto;padding:20px 24px;border-radius:10px;max-height:90vh;overflow:auto;}
body.clinical-page #view-switcher #partners{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end;}
body.clinical-page #view-switcher #partners img{height:28px;width:auto;background:#fff;border-radius:4px;padding:2px;}
</style>
<script src="__PLOTLY_CDN__"></script>
<script src="__JSPDF_CDN__"></script>
</head>
<body class="view-clinical-symptoms clinical-page stub-view">
<header id="site-header">
  <div id="site-header-left">
    <h1 id="page-heading">DRC Ebola Bundibugyo - Epidemic Intelligence Dashboard</h1>
    <div class="sub" id="title-sub" data-i18n-html="clinical.header_sub">Clinical symptoms · data cut <b>__SNAP__</b></div>
  </div>
</header>
<nav id="page-tabs"><div id="view-tabs" class="view-tabs">
__NAV_LINKS__
</div></nav>
<div class="clinical-scroll">

<div id="errbar"></div>
<header class="clinical-title-block">
  <h1 data-i18n="clinical.title">BVD clinical characteristics — DR Congo</h1>
  <div class="sub" id="clinical-subtitle"></div>
</header>
<div class="filterbar">
  <div class="fgroup"><label data-i18n="clinical.filter.province">Province</label><select id="f_prov" multiple autocomplete="off"></select></div>
  <div class="fgroup"><label data-i18n="clinical.filter.age_band">Age band</label><select id="f_age" multiple autocomplete="off"></select></div>
  <div class="fgroup"><label data-i18n="clinical.filter.sex">Sex</label>
    <div class="seg" data-role="sex"><button data-v="all" class="on" data-i18n="clinical.filter.all">All</button>
      <button data-v="0" data-i18n="clinical.filter.female">Female</button><button data-v="1" data-i18n="clinical.filter.male">Male</button></div></div>
  <div class="fgroup"><label><span data-i18n="clinical.filter.hcw">Healthcare worker</span><span class="info" data-tip="Healthcare worker = a health-worker role recorded in the line list's health_worker_position field (e.g. nurse, doctor, hygienist, midwife, lab technician). Blank entries and explicit non-roles (e.g. 'non', 'RAS', 'sans emploi') are treated as non-HCW. Flags occupation, not exposure; n≈172 (~3%), so HCW strata are underpowered.">i</span></label>
    <div class="seg" data-role="hcw"><button data-v="all" class="on" data-i18n="clinical.filter.all">All</button>
      <button data-v="1" data-i18n="clinical.filter.hcw_yes">HCW</button><button data-v="0" data-i18n="clinical.filter.hcw_no">Non-HCW</button></div></div>
  <div class="fgroup"><label><span data-i18n="clinical.filter.vital">Vital-outcome def.</span><span class="info" data-tip="Definition of 'died' for the mortality panels (KPIs, epicurve, mortality-by-admission, symptoms-by-status, deceased table, baseline). 'Recorded death (union)' = reported via the death-alert channel OR deceased at sample collection. The alternatives isolate each source as a sensitivity analysis (the two are only partly concordant). 'No death recorded' never implies survival — there is no outcome follow-up. The §7 Ct panel uses ante-mortem samples and is unaffected by this toggle.">i</span></label>
    <select class="one" id="f_vital">
      <option value="union" data-i18n="clinical.filter.vital_union">Recorded death (union)</option>
      <option value="alert" data-i18n="clinical.filter.vital_alert">Death alert only</option>
      <option value="sampledec" data-i18n="clinical.filter.vital_sample">Deceased at sampling</option>
    </select></div>
  <div class="fgroup"><label data-i18n="clinical.filter.window">Time window</label>
    <div class="seg" data-role="win"><button data-v="all" class="on" data-i18n="clinical.filter.win_all">Entire period</button>
      <button data-v="w4" data-i18n="clinical.filter.win_30">Last 30 d</button><button data-v="w2" data-i18n="clinical.filter.win_14">Last 14 d</button></div></div>
  <button class="btn" id="reset" data-i18n="clinical.filter.reset">Reset</button>
  <div class="nrec" id="nrec"></div>
</div>
<div class="clinical-body">
<div class="wrap">

  <section>
    <div class="sfxhead"><h2 data-i18n="clinical.sections.glance">At a glance</h2><span class="n" data-i18n="clinical.sections.glance_n">current selection</span></div>
    <div class="kpis" id="kpis"></div>
    <div class="note" id="clinical-scope-note"><b>Analytic scope:</b> records that reached sample collection / testing (a sample,
      laboratory record or final classification); never-sampled / invalidated alerts are excluded.
      <b>Two status axes are used throughout.</b> <b>Test status</b> = laboratory-confirmed vs test-negative
      vs <b>unknown</b> (sampled but not yet classified). <b>Vital outcome</b> = <b>died</b> (recorded as a
      death alert <i>or</i> deceased at sample collection) vs <b>no death recorded</b> — the latter does
      <i>not</i> imply survival (outcome may simply be unrecorded), so death proportions are not a
      case-fatality rate. The time window is anchored on notification date.</div>
  </section>

  <section>
    <div class="sfxhead"><h2 data-i18n="clinical.sections.cohort">Who is in this selection, and how complete are the records?</h2><span class="n" data-i18n="clinical.sections.cohort_n">who · missing fields</span></div>
    <p class="desc" data-i18n="clinical.sections.cohort_desc">Side-by-side profile of laboratory-confirmed vs test-negative patients in the current filters, plus how often each analysis field is filled in. Charts below only use records that have the dates or fields they need.</p>
    <div class="grid2">
      <div class="panel"><div class="ptitle" data-i18n-html="clinical.sections.baseline_title">Confirmed vs test-negative profile<span>who looks different between groups</span></div><div id="baseline"></div></div>
      <div class="panel"><div class="ptitle" data-i18n-html="clinical.sections.complete_title">How often is each field filled in?<span>recorded vs missing</span></div><div id="completeness"></div></div>
    </div>
    <div class="note" data-i18n-html="clinical.sections.methods_plain"><b>How to read these analyses.</b> Figures describe associations in observational data — they do not prove cause and effect. Confidence intervals are not adjusted for looking at many symptoms at once, so treat single ‘significant’ cells cautiously and favour overall patterns. <span class="gloss" data-tip="A delay is right-truncated when observation ends (the data cut) before the event can finish happening — e.g. recent admissions may not yet have recorded a death or discharge.">Right truncation</span> and incomplete follow-up matter especially for recent weeks and for onset-based delays (see Methods for technical detail).</div>
  </section>

  <section>
    <div class="sfxhead"><h2 data-i18n="clinical.sections.hcw_section">Healthcare workers (aggregate only)</h2><span class="n" data-i18n="clinical.sections.hcw_section_n">no individual timelines</span></div>
    <p class="desc" data-i18n="clinical.sections.hcw_section_desc">Aggregated view of healthcare workers in the current selection (counts, age/sex mix, top symptoms, recorded deaths). Fine-grained timelines and onset dates are not shown, to reduce re-identification risk when numbers are small.</p>
    <div class="panel"><div id="hcw_agg"></div><div class="cap" id="cap_hcw_agg"></div></div>
  </section>

  <section>
    <div class="sfxhead"><h2 data-i18n="clinical.sections.daily">1 · Daily hospitalisations &amp; deaths</h2><span class="n" data-i18n="clinical.sections.daily_n">by admission / death date</span>
      <div class="ctl"><label data-i18n="clinical.sections.stratify">Stratify by</label>
        <div class="seg" data-role="epistrat"><button data-v="sex" class="on" data-i18n="clinical.sections.strat_sex">Sex</button>
          <button data-v="ab" data-i18n="clinical.sections.strat_age">Age</button><button data-v="hcw" data-i18n="clinical.sections.strat_hcw">Healthcare</button><button data-v="none" data-i18n="clinical.sections.strat_none">None</button></div>
      </div></div>
    <p class="desc" data-i18n="clinical.sections.daily_desc">Daily hospital admissions (by admission date) and recorded deaths (by notification date),
      stacked by the chosen stratum, with a cumulative line on the right axis (cumulative <i>within the selected
      time window</i>). Deaths use the vital-outcome definition set in the filter bar. Respects all filters.</p>
    <div class="grid2">
      <div class="panel"><div class="ptitle">Hospital admissions<span id="cap_adm"></span></div><div id="epi_adm" class="chart"></div></div>
      <div class="panel"><div class="ptitle">Deaths recorded<span id="cap_death"></span></div><div id="epi_death" class="chart"></div></div>
    </div>
  </section>

  <section>
    <div class="sfxhead"><h2 data-i18n="clinical.sections.pyramids">2 · Age &amp; sex distribution, by test status</h2><span class="n" data-i18n="clinical.sections.pyramids_n">pyramids + positivity</span></div>
    <p class="desc" data-i18n="clinical.sections.pyramids_desc">Age-and-sex pyramids for confirmed-positive and test-negative case-patients (mirrors Fig. S1),
      plus test positivity by age band and sex — showing whether the probability of a positive test differs by
      age or sex in the current selection.</p>
    <div class="grid3">
      <div class="panel"><div class="ptitle">Confirmed-positive<span>female ← | → male</span></div><div id="pyr_pos" class="chart"></div></div>
      <div class="panel"><div class="ptitle">Test-negative<span>female ← | → male</span></div><div id="pyr_neg" class="chart"></div></div>
      <div class="panel"><div class="ptitle">Test positivity<span>by age band &amp; sex</span></div><div id="positivity" class="chart"></div></div>
    </div>
  </section>

  <section>
    <div class="sfxhead"><h2 data-i18n="clinical.sections.mort">3 · Mortality by admission date</h2><span class="n" data-i18n="clinical.sections.mort_n">deaths / admissions per week</span></div>
    <p class="desc" data-i18n="clinical.sections.mort_desc">Weekly proportion of admitted individuals recorded as having died, by week of hospital admission
      (Wilson 95% CI), with weekly admission volume for context.</p>
    <div class="panel"><div id="mortadm" class="chart"></div><div class="cap" id="cap_mortadm"></div></div>
    <div class="note" data-i18n-html="clinical.sections.mort_caveat"><b>Interpretation caveat.</b> Recent weeks often look artificially ‘low mortality’ because deaths (and hospital exits) are recorded with lag — incomplete follow-up, not necessarily improving survival. Compare earlier weeks for more stable proportions.</div>
  </section>

  <section>
    <div class="sfxhead"><h2 data-i18n="clinical.sections.sym_table">4 · Signs &amp; symptoms at presentation — confirmed vs negative</h2><span class="n" data-i18n="clinical.sections.sym_table_n">Table 1</span></div>
    <p class="desc" data-i18n="clinical.sections.sym_table_desc">Relative difference in presenting signs and symptoms between laboratory-confirmed and
      test-negative case-patients (records with a completed symptom field). Risk difference uses a Newcombe
      95% CI; risk ratio a Katz-log 95% CI (computed live for the current selection). Green = lower in
      confirmed, red = higher in confirmed.</p>
    <div class="panel"><div id="symtable"></div><div class="cap" id="cap_symtable"></div></div>
    <div class="note"><b>Interpretation caveats.</b> Both groups are <i>suspected</i> BVD patients who met the
      symptom-based case definition, so absolute frequencies are inflated and the confirmed-vs-negative contrast
      may be attenuated by symptoms shared through the case definition. This is a screen over ~20 symptoms with
      no multiplicity adjustment: at 95% confidence, roughly one comparison in twenty is expected to exclude the
      null by chance, so read the overall pattern rather than individual coloured cells.</div>
  </section>

  <section>
    <div class="sfxhead"><h2 data-i18n="clinical.sections.sym_status">5 · Confirmed symptoms &amp; association with death</h2><span class="n" data-i18n="clinical.sections.sym_status_n">prevalence + death RR</span></div>
    <p class="desc" data-i18n-html="clinical.sections.sym_status_desc">Left: how common each presenting symptom is among laboratory-confirmed cases. Right: relative risk of a recorded death among confirmed cases who present with each symptom versus those who do not.</p>
    <div class="note triage" data-i18n-html="clinical.sections.triage_note"><b>Clinical triage.</b> Identifying patients at higher risk of death supports decisions such as closer observation and more intensive nursing. These panels summarise associations in the line list; they do not replace bedside assessment.</div>
    <div class="grid2">
      <div class="panel"><div class="ptitle" data-i18n-html="clinical.sections.prev_title">Symptom prevalence among confirmed<span>records with a symptom field</span></div><div id="symstatus" class="chart"></div></div>
      <div class="panel"><div class="ptitle" data-i18n-html="clinical.sections.deathrr_title">Relative risk of death by presenting symptom<span>confirmed cases · with vs without each symptom</span></div><div id="deathrr" class="chart"></div><div class="cap" id="cap_deathrr"></div></div>
    </div>
  </section>

  <section>
    <div class="sfxhead"><h2 data-i18n="clinical.sections.triage_risk">Symptoms, days since onset, and death</h2><span class="n" data-i18n="clinical.sections.triage_risk_n">triage risk panel</span></div>
    <p class="desc" data-i18n="clinical.sections.triage_risk_desc">Among confirmed cases with a usable symptom-onset date, death recording by days from onset to hospital admission (columns) and by presenting symptom (rows).</p>
    <div class="panel"><div id="triage_risk" class="chart"></div><div class="cap" id="cap_triage_risk"></div></div>
  </section>

  <section>
    <div class="sfxhead"><h2 data-i18n="clinical.sections.cooccur">6 · Symptom co-occurrence</h2><span class="n" data-i18n="clinical.sections.cooccur_n">correlation + combinations</span>
      <div class="ctl"><label data-i18n="clinical.sections.cohort_label">Cohort</label>
        <div class="seg" data-role="symcohort"><button data-v="confirmed" class="on" data-i18n="clinical.sections.cohort_confirmed">Confirmed</button>
          <button data-v="all" data-i18n="clinical.sections.cohort_all">All with symptoms</button></div></div></div>
    <p class="desc" data-i18n-html="clinical.sections.cooccur_desc">Left: pairwise correlation (φ coefficient) between presenting symptoms. Right: an UpSet plot
      of the most frequent combinations of the six most common symptoms. Both default to confirmed cases; switch cohort at right.</p>
    <div class="grid2">
      <div class="panel"><div class="ptitle">Symptom correlation (φ)<span>records with a symptom field</span></div><div id="corr" class="chart"></div></div>
      <div class="panel"><div class="ptitle">Combinations (UpSet)<span>six most frequent symptoms</span></div>
        <div id="upset" class="chart"></div><div class="cap" id="cap_upset"></div></div>
    </div>
    <div class="note" data-i18n-html="clinical.sections.wet_stage_note"><b>Clinical reading (6b).</b> Frequent combinations that include diarrhoea, vomiting or haemorrhagic signs suggest many patients are already in the ‘wet’ symptomatic phase at presentation — relevant for isolation, PPE and triage.</div>
  </section>

  <section>
    <div class="sfxhead"><h2 data-i18n="clinical.sections.ct">7 · Ct values by vital outcome</h2><span class="n" data-i18n="clinical.sections.ct_n">Altona (PCRA) · ante-mortem blood</span></div>
    <p class="desc" data-i18n="clinical.sections.ct_desc">Cycle-threshold (Ct) values among confirmed positives, by vital outcome, for the
      <b>Altona (PCRA)</b> assay. <b>Restricted to ante-mortem blood specimens</b>: deceased-at-collection
      samples are almost entirely <b>post-mortem swabs</b> (a different specimen with degraded RNA), so an
      unrestricted died-vs-alive Ct comparison would confound outcome with specimen type. Lower Ct = higher
      viral load; the caption gives median [IQR] and the crude difference (small ante-mortem death counts, so
      interpret cautiously). Ct is not comparable across assays.</p>
    <div class="panel"><div class="ptitle">Altona (PCRA), HEX target<span id="cap_ctA"></span></div><div id="ct_altona" class="chart"></div></div>
  </section>

  <section>
    <div class="sfxhead"><h2 data-i18n="clinical.sections.onset_sel">Onset documentation — included vs excluded</h2><span class="n" data-i18n="clinical.sections.onset_sel_n">selection check for onset-based analyses</span></div>
    <p class="desc" data-i18n="clinical.sections.onset_sel_desc">The delay distributions (§8–10) condition on a reliable symptom onset (≥ 15 Jun 2026) and
      are complete-case — a minority of confirmed cases. This table compares those that qualify with those
      excluded (standardized differences) so any selection bias is visible.</p>
    <div class="panel supp"><div id="onsetsel"></div><div class="cap" id="cap_onsetsel"></div></div>
  </section>

  <section id="delays">
    <div class="sfxhead"><h2 data-i18n="clinical.sections.delays">8–10 · Clinical delay distributions</h2><span class="n" data-i18n="clinical.sections.delays_n">empirical + epidist / MLE fits</span></div>
    <p class="desc" data-i18n-html="clinical.sections.delays_desc">Empirical delay histograms with parametric fits adjusting for double interval-censoring and right truncation.</p>
    <div class="grid3">
      <div class="panel"><div class="ptitle">Onset → hospital admission
        <span>Stratum: <select class="one" id="strat_onset_to_admission"></select></span></div>
        <div id="d_adm" class="chart"></div><div class="cap" id="cap_d_adm"></div></div>
      <div class="panel"><div class="ptitle">Hospital admission → exit
        <span>Stratum: <select class="one" id="strat_admission_to_exit"></select></span></div>
        <div id="d_exit" class="chart"></div><div class="cap" id="cap_d_exit"></div></div>
      <div class="panel"><div class="ptitle">Onset → death (in-hospital)
        <span>Stratum: <select class="one" id="strat_onset_to_death"></select></span></div>
        <div id="d_death" class="chart"></div><div class="cap" id="cap_d_death"></div></div>
    </div>
    <div class="note"><b>Ct control &amp; assay separation.</b> For onset→admission, Ct strata are split at the
      within-assay median and reported separately for RADIONE and Altona, since Ct is not comparable across
      assays/locations. Where a stratum has too few records for a stable fit, only the empirical distribution
      is shown.</div>
  </section>

  <section>
    <div class="sfxhead"><h2 data-i18n="clinical.sections.adm_sym">11 · Admission delay vs symptoms at onset</h2><span class="n" data-i18n="clinical.sections.adm_sym_n">median onset→admission</span></div>
    <p class="desc" data-i18n="clinical.sections.adm_sym_desc">Whether presenting with a given symptom at onset is associated with a faster or slower
      onset→hospital-admission delay.</p>
    <div class="panel"><div id="admsym" class="chart"></div><div class="cap" id="cap_admsym"></div></div>
    <div class="note" data-i18n-html="clinical.sections.adm_sym_caveat"><b>Interpretation caveat.</b> Self-reported symptom onset is often imprecise. Patterns such as severe signs (e.g. haemorrhage) appearing to start only one or two days before admission are clinically unexpected and usually mean the onset date is unreliable — treat these delay estimates with low confidence.</div>
  </section>

  <section>
    <div class="sfxhead"><h2 data-i18n="clinical.sections.supp_died">Supplementary · signs &amp; symptoms among the deceased</h2><span class="n" data-i18n="clinical.sections.supp_died_n">positive vs negative · died only</span></div>
    <p class="desc" data-i18n="clinical.sections.supp_died_desc">Table 4 restricted to individuals recorded as having died — comparing presenting signs and
      symptoms of confirmed-positive vs test-negative <b>fatal</b> cases (same estimators as Table 4). Sample
      sizes are smaller, so several risk ratios may be imprecise or not estimable.</p>
    <div class="panel supp"><div id="symtable_died"></div><div class="cap" id="cap_symtable_died"></div></div>
  </section>

  <section id="supp">
    <div class="sfxhead"><h2 data-i18n="clinical.sections.supp_rr">Supplementary · age- &amp; sex-adjusted symptom associations</h2><span class="n" data-i18n="clinical.sections.supp_rr_n">modified Poisson · confirmed cases</span></div>
    <p class="desc" data-i18n="clinical.sections.supp_rr_desc">Adjusted risk ratios (mirrors Table S1) for each presenting symptom among confirmed cases,
      from modified Poisson regression (log link, robust variance) with male sex and age (per 10-yr increment)
      entered simultaneously. Precomputed for the selected time window. <i>NE</i> = not estimable (&lt;10 events
      or &lt;3 in a sex stratum).</p>
    <div class="panel supp"><div id="adjrr"></div></div>
    <div class="note"><b>Method &amp; symptom-code note.</b> These are exploratory analyses without prespecified
      multiplicity adjustment: confidence-interval widths are not adjusted for multiplicity and should not be
      used in place of hypothesis testing. Symptom codes follow
      <code>Symptoms_en.csv</code>; three French codes were inferred and flagged with <b>*</b>:
      <b>DT</b>=Chest pain, <b>DRO</b>=Retro-orbital pain, <b>ICT</b>=Jaundice.</div>
  </section>

</div>
</div>

</div>
<div id="methods-modal" class="modal" role="dialog" aria-modal="true" aria-label="Contributors, Data, and Methods">
  <div class="sheet">
    <button class="close" id="methods-close" aria-label="Close">✕</button>
    <h2 id="methods-modal-title" data-i18n="ui.methods_modal_title">Contributors, Data, and Methods</h2>
    <div id="methods-content"></div>
  </div>
</div>
<div id="terms-modal" class="modal" role="dialog" aria-modal="true" aria-label="Terms of Use">
  <div class="sheet">
    <button class="close" id="terms-close" aria-label="Close">✕</button>
    <h2 id="terms-modal-title" data-i18n="ui.terms_modal_title">Terms of Use</h2>
    <div id="terms-updated" style="font-size:11px;color:#888;margin-bottom:10px"></div>
    <div id="terms-content"></div>
  </div>
</div>
<div id="view-switcher">
  <div id="footer-links">
    <div id="lang-switcher" class="lang-switcher" role="group" aria-label="Language">
      <div class="lang-toggle-track">
        <span class="lang-toggle-thumb" aria-hidden="true"></span>
        <button type="button" class="lang-btn active" data-lang="en" aria-pressed="true">EN</button>
        <button type="button" class="lang-btn" data-lang="fr" aria-pressed="false">FR</button>
      </div>
    </div>
    <button id="methods-btn" class="link-btn" type="button" data-i18n="ui.methods_btn">Contributors, Data, and Methods</button>
    <button id="terms-btn" class="link-btn" type="button" data-i18n="ui.terms_btn">Terms of Use</button>
  </div>
  <div id="partners"></div>
</div>
<script type="application/json" id="clinical-chrome-payload">__CHROME_PAYLOAD__</script>
<script>__JS__</script>
</body></html>"""


def build_clinical_html(*, nav_links: str, assets_prefix: str = "assets/",
                        data: dict | None = None, fits: dict | None = None,
                        chrome_payload: dict | None = None) -> str:
    """Assemble the clinical-symptoms page HTML (dashboard nav + clinical content + footer)."""
    if data is None or fits is None:
        data, fits, clin_dir = load_clinical_bundle()
        print(f"  clinical bundle: {clin_dir}")
    chrome_payload = chrome_payload or {}
    js = (JS.replace("__DATA__", json.dumps(data, separators=(",", ":")))
            .replace("__FITS__", json.dumps(fits, separators=(",", ":")))
            .replace("__LOGO__", LOGO_B64))
    html = (HTML.replace("__PLOTLY_CDN__", PLOTLY_CDN)
                .replace("__JSPDF_CDN__", JSPDF_CDN)
                .replace("__CSS__", CSS)
                .replace("__JS__", js)
                .replace("__SNAP__", data["meta"]["snapshot"])
                .replace("__GEN__", data["meta"].get("generated", data["meta"]["snapshot"]))
                .replace("__NRAW__", f'{data["meta"]["n_raw"]:,}')
                .replace("__NSCOPE__", f'{data["meta"]["n_scope"]:,}')
                .replace("__LOGO__", LOGO_B64)
                .replace("__NAV_LINKS__", nav_links)
                .replace("__ASSETS_PREFIX__", assets_prefix)
                .replace("__CHROME_PAYLOAD__", json.dumps(chrome_payload, separators=(",", ":"), ensure_ascii=False)))
    return html


def build():
    """CLI helper: write a standalone preview next to this file."""
    # Late import to avoid circular deps when used from pages/
    import sys
    sys.path.insert(0, str(HERE.parent))
    from common.chrome import _render_nav
    html = build_clinical_html(nav_links=_render_nav("clinical-symptoms", "assets/"))
    out = HERE / "clinical_tab_preview.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    build()
