import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import re, os, warnings
from pathlib import Path

warnings.filterwarnings('ignore')

# ── CONFIG ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Controle Integrado — ES/MG",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── THEME ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stAppViewContainer"] { background:#0a0c10; }
  [data-testid="stSidebar"] { background:#111318; border-right:1px solid #1e2330; }
  [data-testid="stSidebar"] * { color:#dde2f0 !important; }
  .block-container { padding-top:1rem; }
  h1,h2,h3 { color:#dde2f0; }
  .metric-card {
    background:#111318; border:1px solid #1e2330; border-radius:8px;
    padding:12px 16px; margin-bottom:8px;
  }
  .metric-label { font-size:9px; color:#5a6380; text-transform:uppercase; letter-spacing:.08em; font-family:monospace; }
  .metric-value { font-size:20px; font-weight:700; font-family:monospace; letter-spacing:-.5px; }
  .metric-sub   { font-size:10px; color:#5a6380; }
  div[data-testid="metric-container"] {
    background:#111318; border:1px solid #1e2330; border-radius:8px; padding:12px;
  }
  div[data-testid="metric-container"] label { color:#5a6380 !important; font-size:11px; }
  div[data-testid="metric-container"] div[data-testid="stMetricValue"] { color:#dde2f0; font-size:22px; }
  .stDataFrame { background:#111318; }
  .stTabs [data-baseweb="tab-list"] { background:#111318; border-bottom:1px solid #1e2330; gap:0; }
  .stTabs [data-baseweb="tab"] { color:#5a6380; background:transparent; border:none; padding:8px 16px; }
  .stTabs [aria-selected="true"] { color:#4e8cff !important; border-bottom:2px solid #4e8cff !important; background:transparent !important; }
  .upload-info { background:#111318; border:1px solid #1e2330; border-radius:8px; padding:12px; font-size:12px; color:#5a6380; font-family:monospace; }
  .fam-badge { display:inline-block; padding:2px 8px; border-radius:4px; font-size:10px; font-weight:600; font-family:monospace; }
</style>
""", unsafe_allow_html=True)

DATA_DIR = Path(__file__).parent / "data"

# ── HELPERS ──────────────────────────────────────────────────────────────────
def fmt_r(v):
    if v is None or (isinstance(v, float) and np.isnan(v)) or v == 0: return "—"
    return f"R$ {abs(v):,.0f}".replace(",","X").replace(".",",").replace("X",".")

def fmt_m(v):
    if v is None or (isinstance(v, float) and np.isnan(v)) or v == 0: return "—"
    return f"R$ {abs(v)/1e6:.1f}M"

def safe(v):
    try: return float(v) if pd.notna(v) else 0.0
    except: return 0.0

def classify_fam(desc):
    d = str(desc).upper()
    if any(k in d for k in ['ELÉTRIC','ELETRIC','ILUMINAÇ','SPDA','SDAI','TOMADA','QUADRO DE ALIMENT','POSTE DE','BALIZADOR','REFLETOR','CFTV','MOTOR ELÉTRIC','GERADOR','INVERSOR','COMBATE INC']): return 'Elétrica'
    if any(k in d for k in ['PINTURA','TRATAMENTO E PINTURA','TRATAMENTO MECÂNICO','TRATAMENTO DAS ESTRUT','TRATAMENTO EXTERNO','TRATAMENTO INTERNO','IMPERMEABILIZ']): return 'Pintura'
    if any(k in d for k in ['CALDERAR','ESTRUTURA METÁL','TELHA','COBERTURA','CALHA','GALPÃO','REMOÇÕES E RETIRADAS','ATENUAÇ','HÉLICE','VENTOINHA','DEFLETOR','ELIMINADOR','DIFUSOR','ESTRUTURA ABSORVEDORA','SERVIÇOS INICIAIS','TELHAS E ACESSÓRIOS','MOVIMENTAÇ']): return 'Caldeiraria'
    if any(k in d for k in ['CIVIL','PAREDE','ALVENARIA','PISO','ESCADA','RAMPA','FACHADA','TETO','SANITÁRIO','SINALIZAÇÃO','SINAL','BOTA FORA','CANTEIRO','JARDIM','TAPUME','ACESSO','PORTARIA','SALA','DRENAGEM','RALO','RECOMPOSIÇÃO','MOURÃO','PILAR','LIMPEZA','SUBSTITUIÇÃO DE CALHAS']): return 'Civil'
    return 'Outros/Apoio'

FAM_COLORS = {
    'Caldeiraria': '#4e8cff',
    'Pintura':     '#f5a830',
    'Elétrica':    '#2dd4a0',
    'Civil':       '#9b74f7',
    'Outros/Apoio':'#5a6380',
}

PLOT_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#5a6380', size=11, family='monospace'),
    margin=dict(l=10, r=10, t=30, b=10),
    legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(size=10)),
    xaxis=dict(gridcolor='#1e2330', zerolinecolor='#1e2330'),
    yaxis=dict(gridcolor='#1e2330', zerolinecolor='#1e2330'),
)

# ── PARSERS ──────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_dem(file_bytes, fname):
    xf = pd.ExcelFile(file_bytes)
    ss_list, ro_list, ra_list = [], [], []

    if 'INTEGRADO' in xf.sheet_names:
        df = pd.read_excel(file_bytes, sheet_name='INTEGRADO', header=None)
        for i in range(5, len(df)):
            r = df.iloc[i]
            if not str(r[1]).strip() or str(r[1]).strip() == 'nan': continue
            ss_list.append({
                'ss': str(r[1]).strip(), 'desc': str(r[2]).strip()[:70],
                'tomador': str(r[4]).strip(), 'status': str(r[5]).strip(),
                'prev': safe(r[24]), 'real': safe(r[25]),
                'dfis': safe(r[27]), 'ddias': int(r[23]) if pd.notna(r[23]) else None,
                'td': str(r[22]).split(' ')[0] if pd.notna(r[22]) else None,
                'apv': safe(r[51]), 'med': safe(r[52]), 'sld': safe(r[53]),
            })

    if 'BD-RO' in xf.sheet_names:
        df = pd.read_excel(file_bytes, sheet_name='BD-RO', header=None)
        for i in range(1, len(df)):
            r = df.iloc[i]
            if not str(r[0]).strip() or str(r[0]).strip() == 'nan': continue
            ro_list.append({'num': str(r[0]).strip(), 'st': str(r[2]).strip()})

    if 'BD-RA' in xf.sheet_names:
        df = pd.read_excel(file_bytes, sheet_name='BD-RA', header=None)
        for i in range(1, len(df)):
            r = df.iloc[i]
            if not str(r[0]).strip() or str(r[0]).strip() == 'nan': continue
            ra_list.append({'num': str(r[0]).strip(), 'st': str(r[1]).strip(),
                            'prazo': str(r[5]).strip() if pd.notna(r[5]) else '',
                            'sit': str(r[7]).strip() if pd.notna(r[7]) else ''})

    curva = []
    if 'CLASS-FIN' in xf.sheet_names:
        df = pd.read_excel(file_bytes, sheet_name='CLASS-FIN', header=None)
        meses = ['Set/25','Out/25','Nov/25','Dez/25','Jan/26','Fev/26','Mar/26']
        ar = df.iloc[3] if len(df) > 3 else []
        mr = df.iloc[4] if len(df) > 4 else []
        for c in range(2, 9):
            try:
                a = safe(ar.iloc[c]); mv = safe(mr.iloc[c])
                if a > 0: curva.append({'mes': meses[c-2], 'acum': a, 'mv': mv})
            except: pass

    return dict(ss=ss_list, ro=ro_list, ra=ra_list, curva=curva, fname=fname)

@st.cache_data(show_spinner=False)
def load_cgo(file_bytes, fname):
    xf = pd.ExcelFile(file_bytes)
    mensal, linhas, ctrl_ss = [], [], []

    if 'TAB-DIN' in xf.sheet_names:
        df = pd.read_excel(file_bytes, sheet_name='TAB-DIN', header=None)
        for i in range(4, len(df)):
            r = df.iloc[i]
            if not str(r[0]).strip() or str(r[0]).strip() == 'nan': continue
            mensal.append({
                'mes': str(r[0]).strip(),
                'recPrev': safe(r[1]), 'recBruta': safe(r[2]), 'recLiq': safe(r[3]),
                'custoTot': safe(r[4]), 'custoEq': safe(r[5]), 'custoMat': safe(r[6]),
                'custoSub': safe(r[7]), 'custoAlug': safe(r[8]),
                'recPrevAcum': safe(r[10]), 'recBrutaAcum': safe(r[11]),
                'recLiqAcum': safe(r[12]), 'custoAcum': safe(r[13]),
                'resultado': safe(r[14]), 'resAcum': safe(r[15]),
            })

    if 'CGO' in xf.sheet_names:
        df = pd.read_excel(file_bytes, sheet_name='CGO', header=None)
        for i in range(4, len(df)):
            r = df.iloc[i]
            lid = str(r[0]).strip(); desc = str(r[3]).strip()
            if not lid or lid == 'nan' or not desc or desc == 'nan': continue
            vals = [safe(r[c]) for c in range(4, 13)]
            linhas.append({'id': lid, 'desc': desc, 'vals': vals})

    if 'CTRL_SS' in xf.sheet_names:
        df = pd.read_excel(file_bytes, sheet_name='CTRL_SS', header=None)
        for i in range(2, len(df)):
            r = df.iloc[i]
            if not str(r[2]).strip() or str(r[2]).strip() in ['nan','NºSS']: continue
            ctrl_ss.append({
                'tom': str(r[0]).strip(), 'ss': str(r[2]).strip(),
                'tit': str(r[3]).strip()[:60],
                'vb': safe(r[4]), 'sb': safe(r[5]),
                'prev': safe(r[6]), 'real': safe(r[7]),
            })

    return dict(mensal=mensal, linhas=linhas, ctrl_ss=ctrl_ss, fname=fname)

@st.cache_data(show_spinner=False)
def load_ef(file_bytes, fname):
    xf = pd.ExcelFile(file_bytes)
    col, cst, sub = [], [], []
    atu, ret, ped = '', 0, 0

    if 'EFETIVO' in xf.sheet_names:
        df = pd.read_excel(file_bytes, sheet_name='EFETIVO', header=None)
        atu = str(df.iloc[0, 13]).replace('ATUALIZAÇÃO: ','') if pd.notna(df.iloc[0, 13]) else ''
        ret = safe(df.iloc[1, 7]); ped = int(df.iloc[1, 6]) if pd.notna(df.iloc[1, 6]) else 0
        for i in range(5, len(df)):
            r = df.iloc[i]
            if not str(r[3]).strip() or str(r[3]).strip() in ['nan','NOME COMPLETO']: continue
            col.append({'tom': str(r[1]).strip(), 'nome': str(r[3]).strip(),
                        'func': str(r[4]).strip(), 'sb': safe(r[5]),
                        'tipo': str(r[8]).strip(),
                        'adm': str(r[9]).split(' ')[0] if pd.notna(r[9]) else '',
                        'sit': str(r[13]).strip()})

    if 'CUSTO ESTIMADO' in xf.sheet_names:
        df = pd.read_excel(file_bytes, sheet_name='CUSTO ESTIMADO', header=None)
        for i in range(2, len(df)):
            r = df.iloc[i]
            if not str(r[1]).strip() or str(r[1]).strip() == 'nan': continue
            cst.append({'tom': str(r[0]).strip(), 'nome': str(r[1]).strip(),
                        'func': str(r[2]).strip(), 'sit': str(r[3]).strip(),
                        'tipo': str(r[4]).strip(),
                        'adm': str(r[5]).split(' ')[0] if pd.notna(r[5]) else '',
                        'sb': safe(r[6]), 'st2': safe(r[7]), 'ali': safe(r[8]),
                        'tra': safe(r[9]), 'enc': safe(r[13]), 'tot': safe(r[14]), 'hh': safe(r[15])})

    if 'SUBCONTRATADOS' in xf.sheet_names:
        df = pd.read_excel(file_bytes, sheet_name='SUBCONTRATADOS', header=None)
        for i in range(3, len(df)):
            r = df.iloc[i]
            if not str(r[2]).strip() or str(r[2]).strip() in ['nan','NOME']: continue
            sub.append({'tom': str(r[0]).strip(), 'nome': str(r[2]).strip(),
                        'func': str(r[3]).strip(), 'emp': str(r[6]).strip() if pd.notna(r[6]) else '',
                        'adm': str(r[7]).split(' ')[0] if pd.notna(r[7]) else '',
                        'sit': str(r[11]).strip() if pd.notna(r[11]) else ''})

    return dict(col=col, cst=cst, sub=sub, atu=atu, ret=ret, ped=ped, fname=fname)

@st.cache_data(show_spinner=False)
def load_eac_file(file_bytes, fname):
    df = pd.read_excel(file_bytes, sheet_name='SS-Modelo', header=None)
    site = str(df.iloc[0,0]).strip() if pd.notna(df.iloc[0,0]) else ''
    ss_name = str(df.iloc[0,2]).strip() if pd.notna(df.iloc[0,2]) else ''
    valor = safe(df.iloc[0,7])
    iss = safe(df.iloc[1,5]) or 0.05
    rev_m = re.search(r'ES_(\d+)', fname, re.I)
    rev = int(rev_m.group(1)) if rev_m else 0
    years = re.findall(r'20\d\d', ss_name)
    ano = years[0] if years else '—'
    key_m = re.search(r'SS[-\s/]?(\d+)[-/](\d{4})', ss_name, re.I)
    key = f'SS-{key_m.group(1).zfill(3)}-{key_m.group(2)}' if key_m else ss_name[:20]
    items = []
    for _, row in df.iloc[4:].iterrows():
        it = str(row.iloc[0]).strip(); tp = str(row.iloc[1]).strip()
        de = str(row.iloc[4]).strip(); vl = row.iloc[32]
        if tp == 'nan' and it != 'nan' and de != 'nan' and pd.notna(vl) and it.count('.') == 0:
            items.append({'item': it, 'desc': de, 'valor': float(vl), 'familia': classify_fam(de)})
    return dict(key=key, ss=ss_name, site=site, ano=ano, iss=iss, valor=valor, rev=rev, items=items)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏗️ Controle Integrado ES/MG")
    st.markdown("---")

    st.markdown("**📊 Planilhas principais**")

    # Demandas
    dem_default = DATA_DIR / "CONTROLE_INTEGRADO_DE_DEMANDAS__ES-MG_.xlsx"
    dem_up = st.file_uploader("Controle de Demandas", type=['xlsx','xls'], key='dem_up',
                               help="CONTROLE_INTEGRADO_*.xlsx")
    dem_src = dem_up if dem_up else (open(dem_default,'rb') if dem_default.exists() else None)
    dem_name = dem_up.name if dem_up else dem_default.name if dem_default.exists() else "—"

    # Efetivo
    ef_default = DATA_DIR / "EFETIVO_ES-REV_11_03_2026.xlsx"
    ef_up = st.file_uploader("Efetivo / RH", type=['xlsx','xls'], key='ef_up',
                              help="EFETIVO_*.xlsx")
    ef_src = ef_up if ef_up else (open(ef_default,'rb') if ef_default.exists() else None)
    ef_name = ef_up.name if ef_up else ef_default.name if ef_default.exists() else "—"

    # CGO
    cgo_default = DATA_DIR / "CGO-ES_MG-03_03_2026.xlsm"
    cgo_up = st.file_uploader("CGO — Controle Gerencial", type=['xlsx','xls','xlsm'], key='cgo_up',
                               help="CGO-ES_MG-*.xlsm")
    cgo_src = cgo_up if cgo_up else (open(cgo_default,'rb') if cgo_default.exists() else None)
    cgo_name = cgo_up.name if cgo_up else cgo_default.name if cgo_default.exists() else "—"

    st.markdown("---")
    st.markdown("**🏗️ Orçamentos EAC**")
    eac_ups = st.file_uploader("EAC-SS-*.xlsm (múltiplos)", type=['xlsm','xlsx'],
                                accept_multiple_files=True, key='eac_up',
                                help="Carregue vários arquivos de uma vez. Revisões são detectadas automaticamente.")

    st.markdown("---")
    st.markdown("**🔍 Filtros**")
    base_opts = ['Todos', 'UTGC', 'EDIVIT', 'UTGSUL']
    base_filter = st.selectbox("Base / Tomador", base_opts)

    st.markdown("---")
    st.caption(f"Dem.: `{dem_name}`")
    st.caption(f"EF.: `{ef_name}`")
    st.caption(f"CGO: `{cgo_name}`")
    if eac_ups:
        st.caption(f"EAC: {len(eac_ups)} arquivo(s) carregado(s)")

# ── LOAD DATA ─────────────────────────────────────────────────────────────────
dem, cgo, ef = None, None, None

if dem_src:
    try:
        dem = load_dem(dem_src.read() if hasattr(dem_src,'read') else open(dem_src,'rb').read(), dem_name)
    except Exception as e:
        st.error(f"Erro ao ler Demandas: {e}")

if cgo_src:
    try:
        cgo = load_cgo(cgo_src.read() if hasattr(cgo_src,'read') else open(cgo_src,'rb').read(), cgo_name)
    except Exception as e:
        st.error(f"Erro ao ler CGO: {e}")

if ef_src:
    try:
        ef = load_ef(ef_src.read() if hasattr(ef_src,'read') else open(ef_src,'rb').read(), ef_name)
    except Exception as e:
        st.error(f"Erro ao ler Efetivo: {e}")

# Load EAC
eac_data = {}
if eac_ups:
    for up in eac_ups:
        try:
            parsed = load_eac_file(up.read(), up.name)
            key = parsed['key']
            if key in eac_data:
                if parsed['rev'] > eac_data[key]['rev']:
                    eac_data[key] = parsed
            else:
                eac_data[key] = parsed
        except Exception as e:
            st.sidebar.warning(f"Erro em {up.name}: {e}")

# Load default EAC from data dir if none uploaded
if not eac_data:
    eac_files = list(DATA_DIR.glob("EAC-SS-*.xlsm")) + list(DATA_DIR.glob("EAC-SS-*.xlsx"))
    for fp in sorted(eac_files):
        try:
            parsed = load_eac_file(open(fp,'rb').read(), fp.name)
            key = parsed['key']
            if key not in eac_data or parsed['rev'] > eac_data[key]['rev']:
                eac_data[key] = parsed
        except: pass

eac_list = sorted(eac_data.values(), key=lambda x: -x['valor'])

# ── FILTER HELPERS ────────────────────────────────────────────────────────────
def filt_ss(ss_list):
    if base_filter == 'Todos': return ss_list
    return [s for s in ss_list if base_filter.upper() in s.get('tomador','').upper()]

def filt_eac(eac):
    if base_filter == 'Todos': return eac
    site_map = {'UTGSUL': ['UTG-SUL','UTGSUL']}
    targets = site_map.get(base_filter, [base_filter])
    return [e for e in eac if any(t in e['site'].upper() for t in targets)]

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("# 🏗️ Controle Integrado de Demandas — ES/MG")
st.markdown(f"Contrato 4600684819 · R$ 208.960.051,80 · Geison Bezerra &nbsp;|&nbsp; Base: **{base_filter}**")

# ── KPI STRIP ─────────────────────────────────────────────────────────────────
ss_filt = filt_ss(dem['ss'] if dem else [])
eac_filt = filt_eac(eac_list)

c1,c2,c3,c4,c5,c6,c7,c8 = st.columns(8)
with c1:
    sc = {}
    for s in ss_filt: sc[s['status']] = sc.get(s['status'],0)+1
    st.metric("Total SS", len(ss_filt), f"{sc.get('EM ANDAMENTO',0)} ativ · {sc.get('CONCLUÍDA',0)} conc.")
with c2:
    ta = sum(s['apv'] for s in ss_filt)
    st.metric("R$ Aprovado", fmt_m(ta))
with c3:
    tm = sum(s['med'] for s in ss_filt)
    ep = f"{tm/ta*100:.1f}% exec." if ta > 0 else "—"
    st.metric("R$ Medido", fmt_m(tm), ep)
with c4:
    if cgo and cgo['mensal']:
        last = cgo['mensal'][-1]
        st.metric("Rec. Bruta Acum.", fmt_m(last['recBrutaAcum']), f"até {last['mes']}")
    else:
        st.metric("Rec. Bruta Acum.", "—")
with c5:
    if cgo and cgo['mensal']:
        st.metric("Custos Acum.", fmt_m(cgo['mensal'][-1]['custoAcum']))
    else:
        st.metric("Custos Acum.", "—")
with c6:
    if cgo and cgo['mensal']:
        resA = cgo['mensal'][-1]['resAcum']
        st.metric("Resultado Acum.", fmt_m(resA), "positivo" if resA >= 0 else "negativo")
    else:
        st.metric("Resultado Acum.", "—")
with c7:
    if ef:
        at = [c for c in ef['col'] if c['sit'] == 'ATIVO']
        st.metric("Efetivo Ativo", len(at), f"{len([s for s in ef['sub'] if s['sit']=='ATIVO'])} subcontr.")
    else:
        st.metric("Efetivo Ativo", "—")
with c8:
    if eac_list:
        st.metric("Portfólio EAC", fmt_m(sum(e['valor'] for e in eac_filt)), f"{len(eac_filt)} SS")
    else:
        st.metric("Portfólio EAC", "—")

st.markdown("---")

# ── TABS ──────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "📋 Financeiro (SS)",
    "📊 Gráficos",
    "📈 CGO — Resultado",
    "💰 CGO — Custos",
    "🧾 Faturamento SS",
    "🚦 Status SS",
    "⏰ Desvios Prazo",
    "🚨 Alertas",
    "👷 Efetivo",
    "💵 Custos RH",
    "📝 ROs / RAs",
    "📉 Curva S",
    "🏗️ Orçamentos EAC",
])

# ── TAB 0: FINANCEIRO ────────────────────────────────────────────────────────
with tabs[0]:
    if not dem:
        st.info("Carregue a planilha de Demandas na barra lateral.")
    else:
        data = [s for s in ss_filt if s['apv'] > 0 or s['med'] > 0]
        st.caption(f"{len(data)} SS com valores financeiros")
        rows = []
        for s in data:
            p = s['med']/s['apv']*100 if s['apv'] > 0 else 0
            rows.append({
                'SS': s['ss'], 'Descrição': s['desc'], 'Tomador': s['tomador'],
                'Status': s['status'],
                'R$ Aprovado': s['apv'], 'R$ Medido': s['med'], 'R$ Saldo': s['sld'],
                '% Exec.': round(p, 1),
            })
        df_fin = pd.DataFrame(rows)
        st.dataframe(
            df_fin.style.format({
                'R$ Aprovado': lambda v: fmt_r(v),
                'R$ Medido': lambda v: fmt_r(v),
                'R$ Saldo': lambda v: fmt_r(v),
                '% Exec.': '{:.1f}%',
            }).background_gradient(subset=['% Exec.'], cmap='RdYlGn', vmin=0, vmax=100),
            use_container_width=True, height=500,
        )

# ── TAB 1: GRÁFICOS ──────────────────────────────────────────────────────────
with tabs[1]:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Curva S — Previsto vs Realizado**")
        if cgo and cgo['mensal']:
            fig = go.Figure()
            meses = [m['mes'] for m in cgo['mensal']]
            fig.add_trace(go.Scatter(x=meses, y=[m['recPrevAcum'] for m in cgo['mensal']],
                name='Previsto', line=dict(color='#4e8cff', dash='dash', width=2), mode='lines+markers', marker=dict(size=5)))
            fig.add_trace(go.Scatter(x=meses, y=[m['recBrutaAcum'] for m in cgo['mensal']],
                name='Realizado', line=dict(color='#2dd4a0', width=2), mode='lines+markers', marker=dict(size=5),
                fill='tozeroy', fillcolor='rgba(45,212,160,.08)'))
            fig.update_layout(**PLOT_LAYOUT, height=280)
            fig.update_yaxes(tickprefix='R$', tickformat=',.0f')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Carregue o CGO para ver a Curva S.")

    with col2:
        st.markdown("**Resultado mensal**")
        if cgo and cgo['mensal']:
            fig = go.Figure()
            meses = [m['mes'] for m in cgo['mensal']]
            fig.add_bar(x=meses, y=[m['recBruta'] for m in cgo['mensal']], name='Rec. Bruta', marker_color='rgba(56,200,240,.7)')
            fig.add_bar(x=meses, y=[m['custoTot'] for m in cgo['mensal']], name='Custos', marker_color='rgba(245,168,48,.7)')
            fig.add_bar(x=meses, y=[m['resultado'] for m in cgo['mensal']], name='Resultado',
                marker_color=['rgba(45,212,160,.85)' if m['resultado']>=0 else 'rgba(240,79,79,.85)' for m in cgo['mensal']])
            fig.update_layout(**PLOT_LAYOUT, height=280, barmode='group')
            fig.update_yaxes(tickprefix='R$', tickformat=',.0f')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Carregue o CGO.")

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("**Status das SS**")
        if dem:
            sc = {}
            for s in ss_filt: sc[s['status']] = sc.get(s['status'],0)+1
            colors = {'EM ANDAMENTO':'#4e8cff','CONCLUÍDA':'#2dd4a0','ON HOLD':'#38c8f0',
                      'CANCELADA':'#5a6380','NÃO EMITIDA SAMC':'#f04f4f','EM PLANEJAMENTO':'#f5a830'}
            fig = go.Figure(go.Pie(
                labels=list(sc.keys()), values=list(sc.values()),
                marker_colors=[colors.get(k,'#5a6380') for k in sc.keys()],
                hole=0.6, textinfo='label+value', textfont_size=11,
            ))
            fig.update_layout(**PLOT_LAYOUT, height=260, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Carregue Demandas.")

    with col4:
        st.markdown("**Desvio físico (SS em andamento)**")
        if dem:
            at = [s for s in ss_filt if s['status']=='EM ANDAMENTO' and s['prev'] and s['real'] is not None]
            if at:
                fig = go.Figure()
                fig.add_bar(y=[s['ss'] for s in at], x=[round(s['prev']*100,1) for s in at],
                    orientation='h', name='Previsto', marker_color='rgba(78,140,255,.5)', width=0.4)
                fig.add_bar(y=[s['ss'] for s in at],
                    x=[round(s['real']*100,1) for s in at], orientation='h', name='Realizado',
                    marker_color=['rgba(45,212,160,.8)' if s['real']>=s['prev'] else 'rgba(240,79,79,.8)' for s in at],
                    width=0.4)
                fig.update_layout(**PLOT_LAYOUT, height=max(260, len(at)*35+60), barmode='group')
                fig.update_xaxes(ticksuffix='%')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem SS em andamento com dados físicos.")
        else:
            st.info("Carregue Demandas.")

# ── TAB 2: CGO RESULTADO ─────────────────────────────────────────────────────
with tabs[2]:
    if not cgo:
        st.info("Carregue o CGO na barra lateral.")
    else:
        last = cgo['mensal'][-1] if cgo['mensal'] else {}
        totRec = sum(m['recBruta'] for m in cgo['mensal'])
        totCst = sum(m['custoTot'] for m in cgo['mensal'])
        resA = last.get('resAcum',0)
        melhor = max(cgo['mensal'], key=lambda m: m['resultado'], default={})
        pior   = min(cgo['mensal'], key=lambda m: m['resultado'], default={})

        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Rec. Bruta Acum.", fmt_m(totRec))
        c2.metric("Custos Acum.", fmt_m(totCst))
        c3.metric("Resultado Acum.", fmt_m(resA), "positivo" if resA >= 0 else "negativo")
        c4.metric("Melhor mês", melhor.get('mes','—'), fmt_r(melhor.get('resultado',0)))
        c5.metric("Pior mês", pior.get('mes','—'), fmt_r(pior.get('resultado',0)))

        fig = go.Figure()
        meses = [m['mes'] for m in cgo['mensal']]
        fig.add_bar(x=meses, y=[m['recBruta'] for m in cgo['mensal']], name='Rec. Bruta', marker_color='rgba(56,200,240,.7)')
        fig.add_bar(x=meses, y=[m['custoTot'] for m in cgo['mensal']], name='Custos', marker_color='rgba(245,168,48,.7)')
        fig.add_bar(x=meses, y=[m['resultado'] for m in cgo['mensal']], name='Resultado',
            marker_color=['rgba(45,212,160,.85)' if m['resultado']>=0 else 'rgba(240,79,79,.85)' for m in cgo['mensal']])
        fig.update_layout(**PLOT_LAYOUT, height=300, barmode='group')
        fig.update_yaxes(tickprefix='R$', tickformat=',.0f')
        st.plotly_chart(fig, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Resultado mensal detalhado**")
            rows = []
            l35 = next((l for l in cgo['linhas'] if l['id']=='3.5'), None)
            for i, m in enumerate(cgo['mensal']):
                crA = l35['vals'][i] if l35 and i < len(l35['vals']) else None
                rows.append({'Mês': m['mes'], 'Rec. Prev.': fmt_r(m['recPrev']),
                    'Rec. Bruta': fmt_r(m['recBruta']), 'Rec. Líq.': fmt_r(m['recLiq']),
                    'Custos': fmt_r(m['custoTot']), 'Resultado': fmt_r(m['resultado']),
                    'Res. Acum.': fmt_r(m['resAcum']), 'C/R Acum.': f"{crA:.3f}" if crA else '—'})
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

        with col2:
            st.markdown("**Retenções e breakdown**")
            l15 = next((l for l in cgo['linhas'] if l['id']=='1.5'), None)
            l16 = next((l for l in cgo['linhas'] if l['id']=='1.6'), None)
            rows2 = []
            for i, m in enumerate(cgo['mensal']):
                rows2.append({'Mês': m['mes'],
                    'Ret.PIS/ISS': fmt_r(l15['vals'][i] if l15 and i<len(l15['vals']) else 0),
                    'Ret.Contr.': fmt_r(l16['vals'][i] if l16 and i<len(l16['vals']) else 0),
                    'Eq./Cant.': fmt_r(m['custoEq']), 'Materiais': fmt_r(m['custoMat']),
                    'Subcontr.': fmt_r(m['custoSub']), 'Aluguel': fmt_r(m['custoAlug'])})
            st.dataframe(pd.DataFrame(rows2), use_container_width=True)

# ── TAB 3: CGO CUSTOS ────────────────────────────────────────────────────────
with tabs[3]:
    if not cgo:
        st.info("Carregue o CGO.")
    else:
        FAM_CGO = [
            {'id':'2.1','label':'Equipe e Canteiro','color':'#4e8cff'},
            {'id':'2.2','label':'Materiais e Ferr.','color':'#f5a830'},
            {'id':'2.3','label':'Subcontratações','color':'#9b74f7'},
            {'id':'2.4','label':'Aluguel de Equip.','color':'#f07030'},
            {'id':'2.5','label':'Fornec. Especiais','color':'#38c8f0'},
        ]
        meses = [m['mes'] for m in cgo['mensal']]
        for f in FAM_CGO:
            lin = next((l for l in cgo['linhas'] if l['id']==f['id']), None)
            f['vals'] = lin['vals'][:len(meses)] if lin else [0]*len(meses)
            f['total'] = sum(f['vals'])

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Custo acumulado por família**")
            fig = go.Figure(go.Pie(
                labels=[f['label'] for f in FAM_CGO],
                values=[f['total'] for f in FAM_CGO],
                marker_colors=[f['color'] for f in FAM_CGO],
                hole=0.6, textinfo='label+percent', textfont_size=11,
            ))
            fig.update_layout(**PLOT_LAYOUT, height=280, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("**Custo mensal por família**")
            fig = go.Figure()
            for f in FAM_CGO:
                fig.add_bar(x=meses, y=f['vals'], name=f['label'], marker_color=f['color'])
            fig.update_layout(**PLOT_LAYOUT, height=280, barmode='stack')
            fig.update_yaxes(tickprefix='R$', tickformat=',.0f')
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Detalhamento de custos por categoria**")
        cl = [l for l in cgo['linhas'] if l['id'] not in ['1','1.1','1.2','1.3','1.4','1.5','1.6','1.7','1.8','3','3.4','3.5']]
        rows = []
        for l in cl:
            row = {'ID': l['id'], 'Descrição': l['desc']}
            for i, m in enumerate(meses):
                row[m] = fmt_r(l['vals'][i] if i < len(l['vals']) else 0)
            row['Total'] = fmt_r(sum(l['vals']))
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=400)

# ── TAB 4: CTRL SS ───────────────────────────────────────────────────────────
with tabs[4]:
    if not cgo or not cgo['ctrl_ss']:
        st.info("Carregue o CGO.")
    else:
        data = cgo['ctrl_ss'] if base_filter=='Todos' else [s for s in cgo['ctrl_ss'] if base_filter.upper() in s['tom'].upper()]
        data = [s for s in data if s['vb']>0 or s['real']>0 or s['prev']>0]
        st.caption(f"{len(data)} SS")
        rows = []
        for s in data:
            dv = s['real']-s['prev'] if s['real'] and s['prev'] else None
            rows.append({
                'Tomador': s['tom'], 'SS': s['ss'], 'Título': s['tit'],
                'Valor Bruto': fmt_r(s['vb']), 'Saldo': fmt_r(s['sb']),
                '% Prev': f"{s['prev']*100:.1f}%", '% Real': f"{s['real']*100:.1f}%",
                'Desvio': f"{dv*100:+.1f}pp" if dv is not None else '—',
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=500)

# ── TAB 5: STATUS ────────────────────────────────────────────────────────────
with tabs[5]:
    if not dem:
        st.info("Carregue Demandas.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            sc = {}
            for s in ss_filt: sc[s['status']] = sc.get(s['status'],0)+1
            colors = {'EM ANDAMENTO':'#4e8cff','CONCLUÍDA':'#2dd4a0','ON HOLD':'#38c8f0',
                      'CANCELADA':'#5a6380','NÃO EMITIDA SAMC':'#f04f4f','EM PLANEJAMENTO':'#f5a830'}
            fig = go.Figure(go.Pie(labels=list(sc.keys()), values=list(sc.values()),
                marker_colors=[colors.get(k,'#5a6380') for k in sc.keys()],
                hole=0.6, textinfo='label+value', textfont_size=11))
            fig.update_layout(**PLOT_LAYOUT, height=280, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            rows = [{'Status':k,'Qtd':v,'%':f"{v/len(ss_filt)*100:.1f}%"} for k,v in sc.items()]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

        with col2:
            at = [s for s in ss_filt if s['status']=='EM ANDAMENTO' and s['prev'] and s['real'] is not None]
            if at:
                at.sort(key=lambda x: (x['dfis'] or 0))
                rows2 = [{'SS':s['ss'], 'Prev %':f"{s['prev']*100:.1f}%",
                          'Real %':f"{s['real']*100:.1f}%",
                          'Desvio':f"{(s['dfis'] or 0)*100:+.1f}%"} for s in at]
                st.dataframe(pd.DataFrame(rows2), use_container_width=True, height=400)

# ── TAB 6: DESVIOS ───────────────────────────────────────────────────────────
with tabs[6]:
    if not dem:
        st.info("Carregue Demandas.")
    else:
        data = sorted([s for s in ss_filt if s['ddias'] is not None], key=lambda x: -(x['ddias'] or 0))
        st.caption(f"{len(data)} SS com desvio de prazo")
        rows = []
        for s in data:
            rows.append({'SS':s['ss'], 'Descrição':s['desc'], 'Status':s['status'],
                         'Desvio (dias)':s['ddias'], 'Térm. TD':s['td'] or '—'})
        df_dev = pd.DataFrame(rows)
        if not df_dev.empty:
            st.dataframe(df_dev.style.background_gradient(subset=['Desvio (dias)'], cmap='RdYlGn_r'),
                        use_container_width=True, height=450)

# ── TAB 7: ALERTAS ───────────────────────────────────────────────────────────
with tabs[7]:
    col1, col2 = st.columns(2)
    crit, atr = [], []
    if dem:
        for s in ss_filt:
            if s['status'] == 'NÃO EMITIDA SAMC': crit.append(f"🔴 **{s['ss']}** — Não emitida SAMC: {s['desc']}")
            if s['status'] == 'ON HOLD': crit.append(f"🟡 **{s['ss']}** — ON HOLD: {s['desc']}")
            if s['dfis'] and s['dfis'] < -0.3 and s['status']=='EM ANDAMENTO':
                crit.append(f"🔴 **{s['ss']}** — Desvio físico crítico ({s['dfis']*100:.1f}%): {s['desc']}")
            if s['ddias'] and s['ddias'] > 14 and s['status']=='EM ANDAMENTO':
                atr.append(f"🟡 **{s['ss']}** — Atraso {s['ddias']} dias: {s['desc']}")
    if cgo:
        for m in cgo['mensal']:
            if m['resultado'] < 0:
                crit.append(f"🔴 **CGO {m['mes']}** — Resultado negativo: {fmt_r(m['resultado'])}")

    with col1:
        st.markdown("**Alertas críticos**")
        if crit:
            for c in crit: st.markdown(c)
        else:
            st.success("Nenhum alerta crítico")
    with col2:
        st.markdown("**SS com atraso ativo**")
        if atr:
            for a in atr: st.markdown(a)
        else:
            st.success("Nenhuma SS em atraso significativo")

# ── TAB 8: EFETIVO ───────────────────────────────────────────────────────────
with tabs[8]:
    if not ef:
        st.info("Carregue a planilha de Efetivo.")
    else:
        ef_col = ef['col'] if base_filter=='Todos' else [c for c in ef['col'] if base_filter.upper() in c['tom'].upper()]
        at = [c for c in ef_col if c['sit']=='ATIVO']
        moi = len([c for c in at if c['tipo']=='MOI'])
        mod = len([c for c in at if c['tipo']=='MOD'])

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Efetivo ativo", len(at), f"{len(ef_col)-len(at)} inativos")
        c2.metric("MOI", moi)
        c3.metric("MOD", mod)
        c4.metric("Taxa retenção", f"{ef['ret']*100:.1f}%", f"{ef['ped']} pedidos deslig.")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Por tomador e tipo**")
            bt = {}
            for c in at:
                if c['tom'] not in bt: bt[c['tom']] = {'MOD':0,'MOI':0}
                bt[c['tom']][c['tipo']] = bt[c['tom']].get(c['tipo'],0)+1
            rows = [{'Tomador':t,'MOD':v.get('MOD',0),'MOI':v.get('MOI',0),'Total':v.get('MOD',0)+v.get('MOI',0)} for t,v in bt.items()]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

            st.markdown("**Top 10 funções**")
            bf = {}
            for c in at:
                if c['func'] not in bf: bf[c['func']] = {'n':0,'tipo':c['tipo']}
                bf[c['func']]['n'] += 1
            top = sorted(bf.items(), key=lambda x: -x[1]['n'])[:10]
            st.dataframe(pd.DataFrame([{'Função':f,'Qtd':v['n'],'Tipo':v['tipo']} for f,v in top]), use_container_width=True)

        with col2:
            st.markdown("**Colaboradores ativos**")
            rows = [{'Nome':c['nome'],'Função':c['func'],'Tomador':c['tom'],'Tipo':c['tipo'],'Admissão':c['adm'].split('T')[0]} for c in sorted(at, key=lambda x: x['nome'])]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, height=420)

        st.markdown("**Subcontratados**")
        sub_filt = ef['sub'] if base_filter=='Todos' else [s for s in ef['sub'] if base_filter.upper() in s['tom'].upper()]
        st.caption(f"{len(sub_filt)} pessoas")
        rows = [{'Nome':s['nome'],'Função':s['func'],'Empresa':s['emp'],'Tomador':s['tom'],'Admissão':s['adm'].split('T')[0],'Status':s['sit']} for s in sub_filt]
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

# ── TAB 9: CUSTOS RH ─────────────────────────────────────────────────────────
with tabs[9]:
    if not ef:
        st.info("Carregue o Efetivo.")
    else:
        ativa = ef['cst'] if base_filter=='Todos' else [c for c in ef['cst'] if base_filter.upper() in c['tom'].upper()]
        ativa = [c for c in ativa if c['sit']=='ATIVO']
        totI = sum(c['tot'] for c in ativa)
        totS = sum(c['st2'] for c in ativa)
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Folha (Sal+Per)", f"R$ {totS/1e3:.0f}k")
        c2.metric("Custo total", f"R$ {totI/1e3:.0f}k")
        c3.metric("Custo médio", f"R$ {totI/(len(ativa) or 1)/1e3:.1f}k")
        c4.metric("Atualização", ef['atu'] or '—')
        st.caption(f"{len(ativa)} colaboradores ativos")
        rows = [{'Nome':c['nome'],'Função':c['func'],'Tomador':c['tom'],'Tipo':c['tipo'],
                 'Sal. Base':fmt_r(c['sb']),'Sal.+Per.':fmt_r(c['st2']),'Aliment.':fmt_r(c['ali']),
                 'Transp.':fmt_r(c['tra']),'Encargos':fmt_r(c['enc']),'Total':fmt_r(c['tot']),
                 'HH':f"R${c['hh']:.2f}" if c['hh'] else '—'} for c in sorted(ativa, key=lambda x: -x['tot'])]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=500)

# ── TAB 10: ROs / RAs ────────────────────────────────────────────────────────
with tabs[10]:
    if not dem:
        st.info("Carregue Demandas.")
    else:
        cn = {}
        for r in dem['ro']: cn[r['st']] = cn.get(r['st'],0)+1
        tot = len(dem['ro'])
        unq = len(set(r['num'] for r in dem['ro']))
        pnd = cn.get('Aguardando Aprovação',0)+cn.get('Aguardando Confirmação',0)+cn.get('Em Registro',0)

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Total RO", f"{tot:,}")
        c2.metric("Únicos", f"{unq:,}")
        c3.metric("Pendentes", pnd)
        c4.metric("Finalizados", cn.get('Finalizado',0))

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**ROs por status**")
            rows = [{'Status':k,'Qtd':v,'%':f"{v/tot*100:.1f}%"} for k,v in cn.items()]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        with col2:
            st.markdown("**Registros de Ação (RA)**")
            rows2 = [{'RA':r['num'],'Status':r['st'],'Prazo':r['prazo'],'Situação':r['sit'][:30]} for r in dem['ra']]
            st.dataframe(pd.DataFrame(rows2), use_container_width=True)

# ── TAB 11: CURVA S ──────────────────────────────────────────────────────────
with tabs[11]:
    if cgo and cgo['mensal']:
        fig = go.Figure()
        meses = [m['mes'] for m in cgo['mensal']]
        fig.add_trace(go.Scatter(x=meses, y=[m['recPrevAcum'] for m in cgo['mensal']],
            name='Previsto', line=dict(color='#4e8cff', dash='dash', width=2), mode='lines+markers'))
        fig.add_trace(go.Scatter(x=meses, y=[m['recBrutaAcum'] for m in cgo['mensal']],
            name='Realizado', line=dict(color='#2dd4a0', width=2), mode='lines+markers',
            fill='tozeroy', fillcolor='rgba(45,212,160,.08)'))
        fig.update_layout(**PLOT_LAYOUT, height=320)
        fig.update_yaxes(tickprefix='R$', tickformat=',.0f')
        st.plotly_chart(fig, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Medição mensal**")
            rows = [{'Mês':m['mes'],'Rec. Mensal':fmt_r(m['recBruta']),'Acumulado':fmt_r(m['recBrutaAcum'])} for m in cgo['mensal']]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        with col2:
            if dem and dem['curva']:
                st.markdown("**Curva S por fase (Demandas)**")
                rows2 = [{'Mês':c['mes'],'Mês (R$)':fmt_r(c['mv']),'Acumulado':fmt_r(c['acum'])} for c in dem['curva']]
                st.dataframe(pd.DataFrame(rows2), use_container_width=True)
    else:
        st.info("Carregue o CGO.")

# ── TAB 12: EAC ──────────────────────────────────────────────────────────────
with tabs[12]:
    if not eac_filt:
        st.info("Nenhum orçamento EAC carregado. Use a barra lateral para adicionar arquivos EAC-SS-*.xlsm")
    else:
        total_eac = sum(e['valor'] for e in eac_filt)

        # Family filter
        fam_filter = st.radio("Família de serviço", ['Todas','Caldeiraria','Pintura','Elétrica','Civil','Outros/Apoio'],
                               horizontal=True, key='fam_filter')

        # KPIs
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Total SS", len(eac_filt))
        c2.metric("Portfólio Total", fmt_m(total_eac), fmt_r(total_eac))
        c3.metric("Maior SS", fmt_m(eac_filt[0]['valor']), eac_filt[0]['key'])
        c4.metric("Menor SS", fmt_m(eac_filt[-1]['valor']), eac_filt[-1]['key'])

        # Family totals
        fam_totals = {f:0 for f in FAM_COLORS}
        for e in eac_filt:
            for it in e['items']:
                fam_totals[it['familia']] = fam_totals.get(it['familia'],0) + it['valor']
        c5.metric("Caldeiraria", fmt_m(fam_totals['Caldeiraria']), f"{fam_totals['Caldeiraria']/total_eac*100:.1f}%" if total_eac else '—')

        # Family bar chart
        fig = go.Figure(go.Bar(
            x=list(fam_totals.keys()), y=list(fam_totals.values()),
            marker_color=[FAM_COLORS[f] for f in fam_totals.keys()],
            text=[f"R$ {v/1e6:.1f}M<br>{v/total_eac*100:.1f}%" if total_eac else '—' for v in fam_totals.values()],
            textposition='auto',
        ))
        fig.update_layout(**PLOT_LAYOUT, height=220, showlegend=False, title="Distribuição por família")
        fig.update_yaxes(tickprefix='R$', tickformat=',.0f')
        st.plotly_chart(fig, use_container_width=True)

        col1, col2 = st.columns([1,1])
        with col1:
            st.markdown("**Resumo por SS**")
            rows = []
            for e in eac_filt:
                rows.append({'Chave':e['key'],'Descrição':e['ss'][:55],'Site':e['site'],
                             'Ano':e['ano'],f"Rev.":'ES_'+str(e['rev']),
                             'Valor (R$)':e['valor']})
            df_ss = pd.DataFrame(rows)
            st.dataframe(
                df_ss.style.format({'Valor (R$)': lambda v: fmt_r(v)})
                     .background_gradient(subset=['Valor (R$)'], cmap='Blues'),
                use_container_width=True, height=420,
            )

        with col2:
            st.markdown(f"**Grupos de serviço{' — '+fam_filter if fam_filter!='Todas' else ''}**")
            all_items = []
            for e in eac_filt:
                for it in e['items']:
                    if fam_filter == 'Todas' or it['familia'] == fam_filter:
                        all_items.append({
                            'Família': it['familia'], 'Site': e['site'], 'SS': e['key'],
                            'Item': it['item'], 'Descrição': it['desc'][:50],
                            'Valor (R$)': it['valor'],
                            '% da SS': round(it['valor']/e['valor']*100, 1) if e['valor'] else 0,
                        })
            all_items.sort(key=lambda x: -x['Valor (R$)'])
            df_it = pd.DataFrame(all_items)
            if not df_it.empty:
                st.dataframe(
                    df_it.style.format({'Valor (R$)': lambda v: fmt_r(v), '% da SS': '{:.1f}%'}),
                    use_container_width=True, height=420,
                )
            else:
                st.info("Nenhum item para o filtro selecionado.")

        # Top SS chart
        st.markdown("**Top SS por valor**")
        top_n = min(15, len(eac_filt))
        top = eac_filt[:top_n]
        fig2 = go.Figure(go.Bar(
            y=[e['key'] for e in reversed(top)],
            x=[e['valor'] for e in reversed(top)],
            orientation='h',
            marker_color=['#2dd4a0' if e['site']=='UTGC' else '#9b74f7' if e['site']=='EDIVIT' else '#f5a830' for e in reversed(top)],
            text=[fmt_m(e['valor']) for e in reversed(top)],
            textposition='auto',
        ))
        fig2.update_layout(**PLOT_LAYOUT, height=max(280, top_n*35+60))
        fig2.update_xaxes(tickprefix='R$', tickformat=',.0f')
        st.plotly_chart(fig2, use_container_width=True)
