# -*- coding: utf-8 -*-
import os, json, math, requests, numpy as np, pandas as pd, yfinance as yf
from functools import lru_cache
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

# =========================
# FICHIERS & PRESETS
# =========================
DATA_DIR = "data"
MAPPING_PATH = os.path.join(DATA_DIR, "id_mapping.json")
PROFILE_PATH = os.path.join(DATA_DIR, "profile.json")
LAST_SEARCH_PATH = os.path.join(DATA_DIR, "last_search.json")

os.makedirs(DATA_DIR, exist_ok=True)
_defaults = [
    (MAPPING_PATH, {}),
    (PROFILE_PATH, {"profil": "Neutre"}),
    (LAST_SEARCH_PATH, {"last": "TTE.PA"}),
]
for p, default in _defaults:
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(default, f)

UA = {"User-Agent": "Mozilla/5.0"}

# =========================
# SENTIMENT (VADER)
# =========================
try:
    nltk.data.find("sentiment/vader_lexicon.zip")
except LookupError:
    try:
        nltk.download("vader_lexicon")
    except Exception:
        pass
try:
    SIA = SentimentIntensityAnalyzer()
except Exception:
    SIA = None

# =========================
# PROFILS IA
# =========================
PROFILE_PARAMS = {
    "Agressif": {"vol_max": 0.08, "target_mult": 1.10, "stop_mult": 0.92, "entry_mult": 0.990},
    "Neutre":   {"vol_max": 0.05, "target_mult": 1.07, "stop_mult": 0.95, "entry_mult": 0.990},
    "Prudent":  {"vol_max": 0.03, "target_mult": 1.05, "stop_mult": 0.97, "entry_mult": 0.995},
}
def get_profile_params(profile: str):
    return PROFILE_PARAMS.get(profile or "Neutre", PROFILE_PARAMS["Neutre"])

def load_profile():
    try:
        return json.load(open(PROFILE_PATH, "r", encoding="utf-8")).get("profil", "Neutre")
    except Exception:
        return "Neutre"
def save_profile(p):
    try:
        json.dump({"profil": p}, open(PROFILE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_last_search():
    try:
        return json.load(open(LAST_SEARCH_PATH, "r", encoding="utf-8")).get("last", "")
    except Exception:
        return ""
def save_last_search(t):
    try:
        json.dump({"last": t}, open(LAST_SEARCH_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass

# =========================
# LS EXCHANGE → YAHOO (heuristiques FR/DE/UK)
# =========================
def _norm(s): return (s or "").strip().upper()
_PARIS = {"AIR","ORA","MC","TTE","BNP","SGO","ENGI","SU","DG","ACA","GLE","RI","KER","HO","EN","CAP","AI","PUB","VIE","VIV","STM"}

def guess_yahoo_from_ls(ticker: str):
    if not ticker: return None
    t = _norm(ticker)
    if "." in t and not t.endswith(".LS"):   # déjà suffixé côté Yahoo
        return t
    if t.endswith(".LS"):                    # Londres
        return f"{t[:-3]}.L"
    if t == "TOTB":                          # cas connu
        return "TOTB.F"
    if t.endswith("B") and not t.endswith("AB"):  # Heuristique DE
        return f"{t}.F"
    if t in _PARIS:
        return f"{t}.PA"
    if len(t) <= 6 and t.isalpha():
        return f"{t}.PA"
    return t

def load_mapping():
    try:
        return json.load(open(MAPPING_PATH, "r", encoding="utf-8"))
    except Exception:
        return {}
def save_mapping(m):
    json.dump(m, open(MAPPING_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def maybe_guess_yahoo(s):
    s=_norm(s)
    m=load_mapping().get(s)
    return m or guess_yahoo_from_ls(s)

def resolve_identifier(id_or_ticker):
    raw=_norm(id_or_ticker)
    if not raw: return None, {}
    mapping=load_mapping()
    if raw in mapping: return mapping[raw],{"source":"mapping"}
    guess=maybe_guess_yahoo(raw)
    if guess:
        try:
            hist=yf.download(guess,period="5d",interval="1d",auto_adjust=False,progress=False,threads=False)
            if not hist.empty:
                mapping[raw]=guess; save_mapping(mapping)
                return guess,{"source":"heuristic"}
        except Exception: pass
    return None, {}

# =========================
# RECHERCHE YAHOO
# =========================
@lru_cache(maxsize=256)
def yahoo_search(query: str, region="FR", lang="fr-FR", quotesCount=20):
    url = "https://query2.finance.yahoo.com/v1/finance/search"
    params = {"q": query, "quotesCount": quotesCount, "newsCount": 0, "lang": lang, "region": region}
    try:
        r = requests.get(url, params=params, headers=UA, timeout=12)
        r.raise_for_status()
        data = r.json()
        quotes = data.get("quotes", [])
        return [{
            "symbol": q.get("symbol"),
            "shortname": q.get("shortname") or q.get("longname") or "",
            "longname": q.get("longname") or q.get("shortname") or "",
            "exchDisp": q.get("exchDisp") or "",
            "typeDisp": q.get("typeDisp") or "",
        } for q in quotes]
    except Exception:
        return []

def find_ticker_by_name(company_name: str, prefer_markets=("Paris","XETRA","Frankfurt","NasdaqGS","NYSE")):
    if not company_name: return []
    q = company_name.strip()
    res = yahoo_search(q)
    if not res: return []
    eq = [r for r in res if (r.get("typeDisp","").lower() in ("equity","action","stock","actions") or r.get("symbol",""))]
    ranked=[]
    for r in eq:
        score = 0
        exch = (r.get("exchDisp") or "").lower()
        name = (r.get("shortname") or r.get("longname") or "").lower()
        sym  = (r.get("symbol") or "").upper()
        if any(pm.lower() in exch for pm in prefer_markets): score += 3
        if q.lower() in name: score += 2
        if q.lower() in sym.lower(): score += 1
        ranked.append((score, r))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in ranked]

# =========================
# MEMBRES INDICES (CAC40)
# =========================
@lru_cache(maxsize=32)
def _read_tables(url: str):
    html = requests.get(url, headers=UA, timeout=20).text
    return pd.read_html(html)

def _extract_name_ticker(tables):
    table=None
    for df in tables:
        cols={str(c).lower() for c in df.columns}
        if (("company" in cols or "name" in cols) and ("ticker" in cols or "symbol" in cols)):
            table=df.copy(); break
    if table is None: table=tables[0].copy()
    table.rename(columns={c:str(c).lower() for c in table.columns}, inplace=True)
    tcol=next((c for c in table.columns if "ticker" in c or "symbol" in c), table.columns[0])
    ncol=next((c for c in table.columns if "company" in c or "name" in c), table.columns[1])
    out=table[[tcol,ncol]].copy(); out.columns=["ticker","name"]
    out["ticker"]=out["ticker"].astype(str).str.strip()
    return out.dropna().drop_duplicates(subset=["ticker"])

@lru_cache(maxsize=8)
def members_cac40():
    df=_extract_name_ticker(_read_tables("https://en.wikipedia.org/wiki/CAC_40"))
    df["ticker"]=df["ticker"].apply(lambda x: x if "." in x else f"{x}.PA")
    df["index"]="CAC 40"
    return df

def members(index_name: str):
    if index_name=="CAC 40": return members_cac40()
    return pd.DataFrame(columns=["ticker","name","index"])

# =========================
# PRIX (AJUSTÉS) & MÉTRIQUES (CT+LT)
# =========================
@lru_cache(maxsize=64)
def fetch_prices_cached(tickers_tuple, period="260d"):
    tickers=list(tickers_tuple)
    if not tickers: return pd.DataFrame()
    try:
        data=yf.download(
            tickers, period=period, interval="1d",
            auto_adjust=True, group_by="ticker", threads=False, progress=False
        )
    except Exception:
        return pd.DataFrame()
    if data is None or len(data)==0: return pd.DataFrame()
    frames=[]
    if isinstance(data,pd.DataFrame) and {"Open","High","Low","Close"}.issubset(data.columns):
        df=data.copy(); df["Ticker"]=tickers[0]; frames.append(df)
    else:
        for t in tickers:
            try:
                if t in data and isinstance(data[t],pd.DataFrame):
                    df=data[t].copy(); df["Ticker"]=t; frames.append(df)
            except Exception: continue
    if not frames: return pd.DataFrame()
    out=pd.concat(frames); out.reset_index(inplace=True); return out

def fetch_prices(tickers, days=260):
    return fetch_prices_cached(tuple(tickers), period=f"{days}d")

def _calendar_returns(last_rows: pd.DataFrame, full_df: pd.DataFrame) -> pd.DataFrame:
    if full_df.empty or last_rows.empty:
        for k in ("pct_1d","pct_7d","pct_30d"): last_rows[k]=np.nan
        return last_rows
    full=full_df.copy()
    full["Ticker"]=full["Ticker"].astype(str).str.upper()
    full=full.sort_values(["Ticker","Date"])
    last=last_rows.copy()
    last["Ticker"]=last["Ticker"].astype(str).str.upper()

    def lookup_price(tkr, ref_date, days_back):
        target=pd.to_datetime(ref_date)-pd.Timedelta(days=days_back)
        hist=full[full["Ticker"]==tkr][["Date","Close"]].dropna().sort_values("Date")
        if hist.empty: return np.nan
        hist=hist[hist["Date"]<=target]
        if hist.empty:
            return float(full[full["Ticker"]==tkr]["Close"].iloc[0])
        return float(hist["Close"].iloc[-1])

    vals_1, vals_7, vals_30 = [], [], []
    for _, r in last.iterrows():
        tkr, dref, pref = r["Ticker"], r["Date"], float(r["Close"])
        p1, p7, p30 = lookup_price(tkr, dref, 1), lookup_price(tkr, dref, 7), lookup_price(tkr, dref, 30)
        v1  = (pref/p1-1)  if (np.isfinite(pref) and np.isfinite(p1)  and p1>0)  else np.nan
        v7  = (pref/p7-1)  if (np.isfinite(pref) and np.isfinite(p7)  and p7>0)  else np.nan
        v30 = (pref/p30-1) if (np.isfinite(pref) and np.isfinite(p30) and p30>0) else np.nan
        if np.isfinite(v1) and abs(v1)>0.4: v1=np.nan  # clamp
        vals_1.append(v1); vals_7.append(v7); vals_30.append(v30)
    last["pct_1d"], last["pct_7d"], last["pct_30d"] = vals_1, vals_7, vals_30
    return last

def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """1 ligne/ticker : indicateurs CT & LT + variations J/7j/30j + scores IA."""
    cols=["Ticker","Date","Close","ATR14","MA20","MA50","MA120","MA240",
          "gap20","gap50","gap120","gap240","trend_ct","trend_lt",
          "pct_1d","pct_7d","pct_30d","score_ct","score_lt","score_ia"]
    if df is None or df.empty: return pd.DataFrame(columns=cols)
    df=df.copy()
    if "Date" not in df.columns:
        df=df.reset_index().rename(columns={df.index.name or "index":"Date"})
    need={"Ticker","Date","High","Low","Close"}
    if need - set(df.columns): return pd.DataFrame(columns=cols)

    df["Ticker"]=df["Ticker"].astype(str).str.upper()
    df=df.sort_values(["Ticker","Date"])

    # ATR
    df["PrevClose"]=df.groupby("Ticker")["Close"].shift(1)
    df["TR"]=np.maximum(df["High"]-df["Low"], np.maximum((df["High"]-df["PrevClose"]).abs(), (df["Low"]-df["PrevClose"]).abs()))
    df["ATR14"]=df.groupby("Ticker")["TR"].transform(lambda s:s.rolling(14,min_periods=5).mean())

    # MAs
    df["MA20"]=df.groupby("Ticker")["Close"].transform(lambda s:s.rolling(20,min_periods=5).mean())
    df["MA50"]=df.groupby("Ticker")["Close"].transform(lambda s:s.rolling(50,min_periods=10).mean())
    df["MA120"]=df.groupby("Ticker")["Close"].transform(lambda s:s.rolling(120,min_periods=20).mean())
    df["MA240"]=df.groupby("Ticker")["Close"].transform(lambda s:s.rolling(240,min_periods=30).mean())

    last=df.groupby("Ticker").tail(1)[["Ticker","Date","Close","ATR14","MA20","MA50","MA120","MA240"]].copy()
    def gap(a,b): 
        return (a/b-1) if (np.isfinite(a) and np.isfinite(b) and b!=0) else np.nan
    last["gap20"]=gap(last["Close"], last["MA20"])
    last["gap50"]=gap(last["Close"], last["MA50"])
    last["gap120"]=gap(last["Close"], last["MA120"])
    last["gap240"]=gap(last["Close"], last["MA240"])

    # Tendances (CT: MA20/50) (LT: MA120/240)
    last["trend_ct"]=0
    last.loc[np.isfinite(last["MA20"]) & np.isfinite(last["MA50"]) & (last["Close"]>=last["MA20"]) & (last["MA20"]>=last["MA50"]), "trend_ct"]=1
    last.loc[np.isfinite(last["MA20"]) & np.isfinite(last["MA50"]) & (last["Close"]<last["MA20"]) & (last["MA20"]<last["MA50"]), "trend_ct"]=-1

    last["trend_lt"]=0
    last.loc[np.isfinite(last["MA120"]) & np.isfinite(last["MA240"]) & (last["Close"]>=last["MA120"]) & (last["MA120"]>=last["MA240"]), "trend_lt"]=1
    last.loc[np.isfinite(last["MA120"]) & np.isfinite(last["MA240"]) & (last["Close"]<last["MA120"]) & (last["MA120"]<last["MA240"]), "trend_lt"]=-1

    # Returns calendaire
    last=_calendar_returns(last, df)

    # Scores
    last["score_ct"]=(
        0.6*(last["gap20"].fillna(0))+0.4*(last["gap50"].fillna(0))
        + 0.2*(np.sign(last["trend_ct"].fillna(0)))
    )
    last["score_lt"]=(
        0.6*(last["gap120"].fillna(0))+0.4*(last["gap240"].fillna(0))
        + 0.3*(np.sign(last["trend_lt"].fillna(0)))
    )
    # Score IA global (pondère CT & LT)
    last["score_ia"]= 0.45*last["score_ct"].fillna(0) + 0.55*last["score_lt"].fillna(0)

    return last.reset_index(drop=True)[cols]

# =========================
# NEWS (avec dates) & RÉSUMÉ
# =========================
@lru_cache(maxsize=256)
def google_news_titles(query, lang="fr"):
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl={lang}-{lang.upper()}&gl={lang.upper()}&ceid={lang.upper()}:{lang.upper()}"
    try:
        xml = requests.get(url, headers=UA, timeout=12).text
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml)
        items = []
        for it in root.iter("item"):
            title = it.findtext("title") or ""
            link  = it.findtext("link") or ""
            pub   = it.findtext("{http://www.w3.org/2005/Atom}updated") or it.findtext("pubDate") or ""
            items.append((title, link, pub))
        return items[:10]
    except Exception:
        return []

def filter_company_news(ticker, company_name, items):
    if not items: return []
    tkr=(ticker or "").lower()
    name=(company_name or "").lower()
    name_short = name.split(" ")[0] if name else ""
    keep=[]
    for title, link, pub in items:
        tl=title.lower()
        if (tkr and tkr in tl) or (name and name in tl) or (name_short and name_short in tl):
            keep.append((title, link, pub))
    return keep

def news_summary(name, ticker, lang="fr"):
    items = google_news_titles(f"{name} {ticker}", lang) or google_news_titles(name, lang)
    items = filter_company_news(ticker, name, items)
    titles = [t for t, _, _ in items]
    if not titles:
        return ("Pas d’actualité saillante — mouvement technique / macro.", 0.0, [])
    POS=["résultats","bénéfice","contrat","relève","guidance","record","upgrade","partenariat","dividende","approbation"]
    NEG=["profit warning","retard","procès","amende","downgrade","abaisse","enquête","rappel","départ","incident"]
    scores=[]
    for t in titles:
        s=0.0
        if SIA:
            try: s=SIA.polarity_scores(t.lower())["compound"]
            except Exception: s=0.0
        tl=t.lower()
        if any(k in tl for k in POS): s += 0.2
        if any(k in tl for k in NEG): s -= 0.2
        scores.append(s)
    m=float(np.mean(scores)) if scores else 0.0
    txt = ("Hausse soutenue par des nouvelles positives."
           if m>0.15 else
           "Baisse liée à des nouvelles défavorables."
           if m<-0.15 else
           "Actualité mitigée/neutre — mouvement surtout technique.")
    return (txt, m, items)

# =========================
# DÉCISION IA & NIVEAUX
# =========================
def decision_label_from_row(row, held=False, vol_max=0.05):
    """Décision court-terme (MA20/50 + ATR + PRU) — historique V6."""
    px=float(row.get("Close", math.nan))
    ma20=float(row.get("MA20", math.nan)) if pd.notna(row.get("MA20", math.nan)) else math.nan
    ma50=float(row.get("MA50", math.nan)) if pd.notna(row.get("MA50", math.nan)) else math.nan
    atr=float(row.get("ATR14", math.nan)) if pd.notna(row.get("ATR14", math.nan)) else math.nan
    pru=float(row.get("PRU", math.nan)) if "PRU" in row else math.nan
    if not math.isfinite(px): return "👁️ Surveiller"
    vol=(atr/px) if (math.isfinite(atr) and px>0) else 0.03
    trend=(1 if math.isfinite(ma20) and px>=ma20 else 0)+(1 if math.isfinite(ma50) and px>=ma50 else 0)
    score=0.0
    score+=0.5*(1 if trend==2 else 0 if trend==1 else -1)
    if math.isfinite(pru) and pru>0: score+=0.2*(1 if px>pru*1.02 else -1 if px<pru*0.98 else 0)
    score+=0.3*(-1 if vol>vol_max else 1)
    if held:
        if score>0.5: return "🟢 Acheter"
        if score<-0.2: return "🔴 Vendre"
        return "🟠 Garder"
    else:
        if score>0.3: return "🟢 Acheter"
        if score<-0.2: return "🚫 Éviter"
        return "👁️ Surveiller"

def decision_label_combined(row, held=False, vol_max=0.05):
    """Décision combinée CT+LT avec score_ia & trend_lt."""
    base = decision_label_from_row(row, held=held, vol_max=vol_max)
    lt = int(row.get("trend_lt", 0))
    sia = float(row.get("score_ia", 0))
    # renforcement LT
    if "Acheter" in base and (lt>=1 and sia>0):
        return "🟢 Acheter (LT ✅)"
    if ("Garder" in base or "Surveiller" in base) and lt>=1 and sia>0.2:
        return "🟢 Acheter / Renforcer (LT)"
    if ("Acheter" in base) and lt==-1 and sia<-0.2:
        return "🟠 Acheter (contre-tendance LT)"
    return base

def price_levels_from_row(row, profile="Neutre"):
    p=get_profile_params(profile)
    px=float(row.get("Close", math.nan))
    ma20=float(row.get("MA20", math.nan)) if pd.notna(row.get("MA20", math.nan)) else math.nan
    base=ma20 if math.isfinite(ma20) else px
    if not math.isfinite(base): return {"entry":math.nan,"target":math.nan,"stop":math.nan}
    return {"entry":round(base*p["entry_mult"],2),"target":round(base*p["target_mult"],2),"stop":round(base*p["stop_mult"],2)}

# =========================
# STYLE TABLEAUX (couleurs)
# =========================
def style_variations(df, cols):
    def color_var(v):
        if pd.isna(v): return ""
        if v>0: return "background-color:#e8f5e9; color:#0b8f3a"
        if v<0: return "background-color:#ffebee; color:#d5353a"
        return "background-color:#e8f0fe; color:#1e88e5"
    sty=df.style
    for c in cols:
        if c in df.columns: sty=sty.applymap(color_var, subset=[c])
    return sty

# Adaptation clair/sombre pour proximité (fond neutre)
def proximity_style(val):
    if pd.isna(val): return ""
    if abs(val) <= 2:  return "background-color:rgba(16,185,129,.18); color:#10B981;"   # vert doux
    if abs(val) <= 5:  return "background-color:rgba(245,158,11,.16); color:#F59E0B;"   # ambre
    return "background-color:rgba(239,68,68,.16); color:#EF4444;"                        # rouge

def highlight_near_entry_row(row):
    if pd.notna(row.get("Proximité (%)")) and abs(row["Proximité (%)"]) <= 2:
        return ["background-color:rgba(250,204,21,.18); font-weight:600"] * len(row)     # jaune doux
    return [""] * len(row)

# =========================
# SÉLECTION IA (TOP N)
# =========================
def select_top_actions(df, profile="Neutre", n=10):
    if df is None or df.empty: return pd.DataFrame()
    p = get_profile_params(profile); vol_max = p["vol_max"]
    data = df.copy()
    need = ["Close","ATR14","trend_ct","trend_lt","score_ct","score_lt","score_ia","MA20","MA50","MA120","MA240"]
    for c in need:
        if c not in data.columns: data[c]=np.nan
    data = data.dropna(subset=["Close"])
    data["Volatilité"] = data["ATR14"]/data["Close"]
    # Filtre de qualité : LT haussier ou neutre et volatilité sous 1.5*seuil
    data = data[(data["Volatilité"] <= vol_max*1.5)]
    # Tri par score IA global
    data = data.sort_values("score_ia", ascending=False)

    def _levels(r):
        lev = price_levels_from_row(r, profile)
        prox = ((r["Close"]/lev["entry"])-1)*100 if (lev["entry"] and lev["entry"]>0) else np.nan
        pot_eur = (lev["target"]-lev["entry"]) if (lev["entry"] and lev["target"]) else np.nan
        return pd.Series({
            "Entrée (€)": lev["entry"], "Objectif (€)": lev["target"], "Stop (€)": lev["stop"],
            "Potentiel (€)": pot_eur, "Proximité (%)": prox
        })

    top = pd.concat([data.reset_index(drop=True), data.apply(_levels, axis=1)], axis=1).head(n)
    keep = ["Ticker","Close","MA20","MA50","MA120","MA240","trend_ct","trend_lt","score_ct","score_lt","score_ia",
            "Entrée (€)","Objectif (€)","Stop (€)","Potentiel (€)","Proximité (%)"]
    for k in keep:
        if k not in top.columns: top[k]=np.nan
    top = top[keep]
    top.rename(columns={"Ticker":"Symbole","Close":"Cours (€)","trend_ct":"Tendance CT","trend_lt":"Tendance LT",
                        "score_ct":"Score CT","score_lt":"Score LT","score_ia":"Score IA"}, inplace=True)
    # format
    for c in ["Cours (€)","Entrée (€)","Objectif (€)","Stop (€)","Potentiel (€)"]:
        top[c]=top[c].astype(float).round(2)
    for c in ["Score CT","Score LT","Score IA","Proximité (%)"]:
        top[c]=top[c].astype(float).round(2)
    # emojis tendance LT
    def emo(v): return "🌱" if v>0 else ("🌧" if v<0 else "⚖️")
    top["LT"] = top["Tendance LT"].apply(emo)
    # prêt à entrer
    top["Signal Entrée"] = top["Proximité (%)"].apply(lambda p: "🟢" if (pd.notna(p) and abs(p)<=2) else ("⚠️" if (pd.notna(p) and abs(p)<=5) else "🔴"))
    return top.reset_index(drop=True)
