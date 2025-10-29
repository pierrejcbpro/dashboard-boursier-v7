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

    # ✅ Correction vectorisée
    last["gap20"]  = np.where(last["MA20"].notna()  & (last["MA20"]  != 0), last["Close"]/last["MA20"]  - 1, np.nan)
    last["gap50"]  = np.where(last["MA50"].notna()  & (last["MA50"]  != 0), last["Close"]/last["MA50"]  - 1, np.nan)
    last["gap120"] = np.where(last["MA120"].notna() & (last["MA120"] != 0), last["Close"]/last["MA120"] - 1, np.nan)
    last["gap240"] = np.where(last["MA240"].notna() & (last["MA240"] != 0), last["Close"]/last["MA240"] - 1, np.nan)

    # Tendances (CT: MA20/50) (LT: MA120/240)
    last["trend_ct"]=0
    last.loc[np.isfinite(last["MA20"]) & np.isfinite(last["MA50"]) & (last["Close"]>=last["MA20"]) & (last["MA20"]>=last["MA50"]), "trend_ct"]=1
    last.loc[np.isfinite(last["MA20"]) & np.isfinite(last["MA50"]) & (last["Close"]<last["MA20"]) & (last["MA20"]<last["MA50"]), "trend_ct"]=-1

    last["trend_lt"]=0
    last.loc[np.isfinite(last["MA120"]) & np.isfinite(last["MA240"]) & (last["Close"]>=last["MA120"]) & (last["MA120"]>=last["MA240"]), "trend_lt"]=1
    last.loc[np.isfinite(last["MA120"]) & np.isfinite(last["MA240"]) & (last["Close"]<last["MA120"]) & (last["MA120"]<last["MA240"]), "trend_lt"]=-1

    # Returns calendaire
    last=_calendar_returns(last, df)

    # Scores IA
    last["score_ct"]=(0.6*last["gap20"].fillna(0)+0.4*last["gap50"].fillna(0)+0.2*np.sign(last["trend_ct"].fillna(0)))
    last["score_lt"]=(0.6*last["gap120"].fillna(0)+0.4*last["gap240"].fillna(0)+0.3*np.sign(last["trend_lt"].fillna(0)))
    last["score_ia"]=0.45*last["score_ct"].fillna(0)+0.55*last["score_lt"].fillna(0)

    return last.reset_index(drop=True)[cols]
