"""
Dashboard Interaktif - Ranked Match League of Legends
Dataset : ranked_match_data_kaggle.csv (Kaggle)
Jalankan: streamlit run app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Dashboard Ranked Match LoL",
    page_icon="🎮",
    layout="wide",
)

CSV_PATH = Path(__file__).parent / "ranked_match_data_kaggle.csv"
ROLES = {"top": "Top", "jungle": "Jungle", "mid": "Mid", "adc": "ADC", "support": "Support"}
CHAMP_FIX = {
    "SIon": "Sion", "Lee sin": "Lee Sin", "Chogath": "Cho'Gath", "Kaisa": "Kai'Sa",
    "Khazix": "Kha'Zix", "Velkoz": "Vel'Koz", "Belveth": "Bel'Veth", "Kogmaw": "Kog'Maw",
    "Kesante": "K'Sante", "Jarvan": "Jarvan IV", "Dr Mundo": "Dr. Mundo",
}


# ----------------------------------------------------------------------------
# 1. LOAD + CLEANING + RESHAPE (wide -> long)
# ----------------------------------------------------------------------------
@st.cache_data
def load_data() -> pd.DataFrame:
    raw = pd.read_csv(CSV_PATH, encoding="utf-8-sig").drop_duplicates()

    frames = []
    for team in (1, 2):
        opp = 2 if team == 1 else 1
        for key, label in ROLES.items():
            p = f"{key}{team}_"
            frames.append(
                pd.DataFrame(
                    {
                        "match_id": raw["match_id"],
                        "team": f"Team {team}",
                        "role": label,
                        "champion": raw[p + "champion"],
                        "kills": raw[p + "kill"],
                        "deaths": raw[p + "death"],
                        "assists": raw[p + "assist"],
                        "gold": raw[p + "gold"],
                        "hasil": raw[f"team{team}_result"].map({1: "Menang", 0: "Kalah"}),
                        "team_kills": raw[f"team{team}_score"],
                        "opp_kills": raw[f"team{opp}_score"],
                    }
                )
            )
    df = pd.concat(frames, ignore_index=True)

    # --- Cleaning ---
    # a) Standarisasi nama champion
    df["champion"] = df["champion"].str.strip().replace(CHAMP_FIX)
    # b) Assist tidak mungkin melebihi total kill tim -> data error (mis. 9372) jadi NaN
    df.loc[df["assists"] > df["team_kills"], "assists"] = pd.NA
    # c) Gold tidak wajar (terlalu kecil / terlalu besar, salah input) jadi NaN
    df.loc[(df["gold"] < 2000) | (df["gold"] > 45000), "gold"] = pd.NA

    # --- Fitur turunan ---
    df["kda"] = (df["kills"] + df["assists"]) / df["deaths"].clip(lower=1)
    df["match_no"] = df["match_id"].str.extract(r"(\d+)").astype(int)
    return df.sort_values(["match_no", "team", "role"]).reset_index(drop=True)


df = load_data()

# ----------------------------------------------------------------------------
# 2. JUDUL & DESKRIPSI
# ----------------------------------------------------------------------------
st.title("🎮 Dashboard Analisis Ranked Match League of Legends")
st.markdown(
    """
Dashboard ini menganalisis performa pemain pada **508 pertandingan ranked** League of Legends
(dataset dari Kaggle: *Ranked Match Data*). Setiap pertandingan dimainkan 2 tim x 5 role
(Top, Jungle, Mid, ADC, Support), sehingga data dibentuk menjadi **5.080 baris data pemain**.
Gunakan filter di sidebar untuk mengeksplorasi kill, death, assist, KDA, dan gold berdasarkan
role, hasil pertandingan, sisi tim, dan champion.
"""
)

# ----------------------------------------------------------------------------
# 3. FILTER INTERAKTIF (sidebar)
# ----------------------------------------------------------------------------
st.sidebar.header("🔎 Filter Data")
role_sel = st.sidebar.multiselect("Role", list(ROLES.values()), default=list(ROLES.values()))
hasil_sel = st.sidebar.multiselect("Hasil Pertandingan", ["Menang", "Kalah"], default=["Menang", "Kalah"])
team_sel = st.sidebar.multiselect("Sisi Tim", ["Team 1", "Team 2"], default=["Team 1", "Team 2"])
champ_sel = st.sidebar.multiselect(
    "Champion (kosongkan = semua)", sorted(df["champion"].unique())
)
kill_min, kill_max = st.sidebar.slider(
    "Rentang Kill Pemain", int(df["kills"].min()), int(df["kills"].max()),
    (int(df["kills"].min()), int(df["kills"].max())),
)
min_pick = st.sidebar.slider("Minimal jumlah pick (untuk win rate champion)", 5, 50, 15)

f = df[
    df["role"].isin(role_sel)
    & df["hasil"].isin(hasil_sel)
    & df["team"].isin(team_sel)
    & df["kills"].between(kill_min, kill_max)
]
if champ_sel:
    f = f[f["champion"].isin(champ_sel)]

if f.empty:
    st.warning("Tidak ada data yang sesuai dengan filter. Silakan ubah filter.")
    st.stop()

# ----------------------------------------------------------------------------
# 4. KPI
# ----------------------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Jumlah Match", f"{f['match_id'].nunique():,}")
k2.metric("Rata-rata Kill", f"{f['kills'].mean():.2f}")
k3.metric("Rata-rata Death", f"{f['deaths'].mean():.2f}")
k4.metric("Rata-rata KDA", f"{f['kda'].mean():.2f}")
k5.metric("Rata-rata Gold", f"{f['gold'].mean():,.0f}")
st.divider()

# ----------------------------------------------------------------------------
# 5. VISUALISASI
# ----------------------------------------------------------------------------
# Baris 1: Bar chart + Pie chart
c1, c2 = st.columns(2)

with c1:
    st.subheader("📊 Win Rate Champion Tertinggi (Bar Chart)")
    champ = (
        f.groupby("champion")
        .agg(pick=("match_id", "count"), win_rate=("hasil", lambda s: (s == "Menang").mean() * 100))
        .query("pick >= @min_pick")
        .sort_values("win_rate", ascending=False)
        .head(10)
        .reset_index()
    )
    if champ.empty:
        st.info("Tidak ada champion yang memenuhi minimal pick. Kecilkan slider minimal pick.")
    else:
        fig = px.bar(
            champ.sort_values("win_rate"), x="win_rate", y="champion", orientation="h",
            color="win_rate", color_continuous_scale="Tealgrn", text=champ.sort_values("win_rate")["win_rate"].round(1),
            hover_data=["pick"], labels={"win_rate": "Win Rate (%)", "champion": "Champion"},
        )
        fig.update_layout(coloraxis_showscale=False, height=400)
        st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("🥧 Proporsi Pick per Role (Pie Chart)")
    role_cnt = f["role"].value_counts().reset_index()
    role_cnt.columns = ["role", "jumlah"]
    fig = px.pie(role_cnt, names="role", values="jumlah", hole=0.35)
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

# Baris 2: Line chart + Histogram
c3, c4 = st.columns(2)

with c3:
    st.subheader("📈 Tren Rata-rata KDA per Kelompok Match (Line Chart)")
    tmp = f.copy()
    tmp["kelompok"] = ((tmp["match_no"] - 1) // 50) * 50 + 1
    tmp["kelompok"] = tmp["kelompok"].astype(str) + "-" + (tmp["kelompok"] + 49).astype(str)
    trend = tmp.groupby(["kelompok", "hasil"], sort=False)["kda"].mean().reset_index()
    fig = px.line(trend, x="kelompok", y="kda", color="hasil", markers=True,
                  labels={"kelompok": "Kelompok Match (per 50)", "kda": "Rata-rata KDA", "hasil": "Hasil"})
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

with c4:
    st.subheader("📉 Distribusi Gold Pemain (Histogram)")
    fig = px.histogram(f.dropna(subset=["gold"]), x="gold", color="hasil", nbins=40,
                       barmode="overlay", opacity=0.7, labels={"gold": "Gold", "hasil": "Hasil"})
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

# Baris 3: Scatter + Heatmap
c5, c6 = st.columns(2)

with c5:
    st.subheader("🔵 Gold vs Kill (Scatter Plot)")
    sc = f.dropna(subset=["gold"])
    if len(sc) > 2000:
        sc = sc.sample(2000, random_state=42)
    fig = px.scatter(sc, x="gold", y="kills", color="role", symbol="hasil", opacity=0.7,
                     hover_data=["champion", "match_id"],
                     labels={"gold": "Gold", "kills": "Kill", "role": "Role", "hasil": "Hasil"})
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)

with c6:
    st.subheader("🔥 Rata-rata KDA: Role x Hasil (Heatmap)")
    heat = f.pivot_table(index="role", columns="hasil", values="kda", aggfunc="mean")
    fig = px.imshow(heat, text_auto=".2f", color_continuous_scale="YlOrRd", aspect="auto",
                    labels={"color": "KDA", "x": "Hasil", "y": "Role"})
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------------------------------------------
# 6. DATA TABLE + DOWNLOAD
# ----------------------------------------------------------------------------
st.divider()
st.subheader("🗂️ Data Hasil Filter")
st.caption(f"{len(f):,} baris data pemain setelah cleaning.")
show = f.drop(columns=["match_no"]).round(2)
st.dataframe(show, use_container_width=True, height=300)
st.download_button("⬇️ Download data (CSV)", show.to_csv(index=False).encode("utf-8"),
                   "data_filter.csv", "text/csv")
