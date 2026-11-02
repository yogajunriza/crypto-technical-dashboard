import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Crypto Technical Dashboard", page_icon="📊", layout="wide")
st.title("📊 Crypto Technical Dashboard")
st.caption("Pemantauan data pasar dan indikator teknikal untuk pembelajaran. Tidak mengeksekusi transaksi.")

@st.cache_data(ttl=60)
def get_data(symbol, timeframe, limit):
    ex = ccxt.indodax({"enableRateLimit": True, "timeout": 20000})
    ex.load_markets()
    if symbol not in ex.markets:
        raise ValueError(f"Pair {symbol} tidak tersedia di Indodax.")
    rows = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    if not rows:
        raise ValueError("Data candle kosong.")
    df = pd.DataFrame(rows, columns=["timestamp","open","high","low","close","volume"])
    df["time"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_convert("Asia/Jakarta")
    return df

def indicators(df):
    df = df.copy()
    delta = df.close.diff()
    gain, loss = delta.clip(lower=0), -delta.clip(upper=0)
    ag = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    al = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = ag / al.replace(0, np.nan)
    df["RSI14"] = 100 - 100/(1+rs)
    for n in [20, 50, 200]:
        df[f"EMA{n}"] = df.close.ewm(span=n, adjust=False).mean()
    e12 = df.close.ewm(span=12, adjust=False).mean()
    e26 = df.close.ewm(span=26, adjust=False).mean()
    df["MACD"] = e12-e26
    df["MACD_signal"] = df.MACD.ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df.MACD-df.MACD_signal
    mid = df.close.rolling(20).mean()
    sd = df.close.rolling(20).std()
    df["BB_mid"], df["BB_upper"], df["BB_lower"] = mid, mid+2*sd, mid-2*sd
    return df

with st.sidebar:
    st.header("Pengaturan")
    pair = st.selectbox("Pasangan aset", ["BTC/IDR","ETH/IDR","SOL/IDR","XRP/IDR","DOGE/IDR","ADA/IDR"])
    tf = st.selectbox("Timeframe", ["5m","15m","1h","4h","1d"], index=2)
    limit = st.slider("Jumlah candle", 100, 500, 250, 50)
    if st.button("Perbarui data"):
        st.cache_data.clear()

try:
    df = indicators(get_data(pair, tf, limit))
    last, prev = df.iloc[-1], df.iloc[-2]
    st.caption(f"{pair} · {tf} · Data terakhir {last.time:%d-%m-%Y %H:%M:%S} WIB")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Harga terakhir", f"{last.close:,.2f} IDR", f"{last.close-prev.close:,.2f}")
    c2.metric("Volume candle", f"{last.volume:,.4f}")
    c3.metric("RSI 14", "—" if pd.isna(last.RSI14) else f"{last.RSI14:.2f}")
    c4.metric("MACD", f"{last.MACD:.4f}")

    st.subheader("Candlestick dan EMA")
    fig = go.Figure(go.Candlestick(x=df.time, open=df.open, high=df.high, low=df.low, close=df.close, name="Harga"))
    for col in ["EMA20","EMA50","EMA200"]:
        fig.add_trace(go.Scatter(x=df.time, y=df[col], mode="lines", name=col))
    fig.update_layout(height=520, xaxis_rangeslider_visible=False, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("RSI 14")
    rf = go.Figure(go.Scatter(x=df.time, y=df.RSI14, name="RSI"))
    rf.add_hline(y=70, line_dash="dash")
    rf.add_hline(y=30, line_dash="dash")
    rf.update_layout(height=260, yaxis_range=[0,100])
    st.plotly_chart(rf, use_container_width=True)

    st.subheader("MACD")
    mf = go.Figure()
    mf.add_trace(go.Scatter(x=df.time, y=df.MACD, name="MACD"))
    mf.add_trace(go.Scatter(x=df.time, y=df.MACD_signal, name="Signal line"))
    mf.add_bar(x=df.time, y=df.MACD_hist, name="Histogram")
    mf.update_layout(height=280, hovermode="x unified")
    st.plotly_chart(mf, use_container_width=True)

    st.subheader("Pembacaan indikator")
    r = last.RSI14
    if pd.isna(r): desc = "Data RSI belum cukup."
    elif r >= 70: desc = "Momentum relatif tinggi; area yang sering disebut jenuh beli."
    elif r <= 30: desc = "Momentum relatif rendah; area yang sering disebut jenuh jual."
    else: desc = "RSI berada di area tengah, tidak ekstrem."
    st.write(f"**RSI:** {desc}")
    st.write("**MACD:**", "MACD di atas signal line." if last.MACD > last.MACD_signal else "MACD di bawah signal line.")
    st.write("**EMA 20:**", "Harga di atas EMA20." if last.close > last.EMA20 else "Harga di bawah EMA20.")
    st.info("Keterangan ini bersifat deskriptif, bukan kepastian arah harga atau rekomendasi transaksi.")

    with st.expander("Tabel data indikator"):
        st.dataframe(df[["time","open","high","low","close","volume","RSI14","EMA20","EMA50","EMA200","MACD","MACD_signal","BB_upper","BB_lower"]].tail(50), use_container_width=True)
        st.download_button("Unduh CSV", df.to_csv(index=False).encode(), f"{pair.replace('/','_')}_{tf}.csv", "text/csv")
except Exception as e:
    st.error(f"Gagal mengambil data: {e}")
    st.caption("Periksa koneksi internet atau ketersediaan pair di Indodax.")
