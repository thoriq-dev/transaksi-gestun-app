from __future__ import annotations
import streamlit as st
st.set_page_config(page_title="Input Data Transaksi", layout="centered")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@600;700&display=swap');
    html, body,
    p, label,
    h1, h2, h3, h4, h5, h6,
    strong, em,
    li, a,
    button,
    input, textarea, select,
    [class*="css"] {
      font-family: 'Noto Sans JP', sans-serif !important;
      font-weight: 600 !important;
    }
    h1, h2 { font-weight: 700 !important; }
    .stTextInput>div>div>input,
    .stNumberInput>div>div>input,
    .stTextArea>div>textarea {
      font-family: 'Noto Sans JP', sans-serif !important;
      font-weight: 600 !important;
    }
    .stSelectbox>div>div>div>div,
    .stRadio>label,
    .stMultiSelect>div>div {
      font-family: 'Noto Sans JP', sans-serif !important;
      font-weight: 600 !important;
    }
    [data-testid="stMarkdownContainer"] h3 {
        color: var(--text-color);
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --text-color: #f5f5f5;  /* warna terang di dark mode */
        }
    }
    @media (prefers-color-scheme: light) {
        :root {
            --text-color: #222222;  /* warna gelap di light mode */
        }
    }
    </style>
""", unsafe_allow_html=True)
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+
import streamlit.components.v1 as components
import random
from typing import List, Tuple, Dict
import pandas as pd
if "debug_help" not in st.session_state:
    st.session_state.debug_help = False
_ORIG_ST_WRITE = st.write
_ORIG_ST_HELP  = st.help
def _noop(*args, **kwargs):
    return
def _safe_write(*args, **kwargs):
    if not st.session_state.get("debug_help", False):
        args = [a for a in args if not callable(a)]
        kwargs = {k: v for k, v in kwargs.items() if not callable(v)}
        if not args and not kwargs:
            return
    return _ORIG_ST_WRITE(*args, **kwargs)
def apply_dev_shield():
    if st.session_state.get("debug_help", False):
        st.write = _ORIG_ST_WRITE
        st.help  = _ORIG_ST_HELP
    else:
        st.write = _safe_write
        st.help  = _noop
apply_dev_shield()
def estimasi_durasi(layanan):
    if layanan == "Super Kilat":
        return timedelta(minutes=20)
    elif layanan == "Kilat":
        return timedelta(minutes=40)
    else:
        return timedelta(hours=3, minutes=0)
def estimasi_selesai(waktu_mulai, durasi):
    waktu_selesai = waktu_mulai + durasi
    return waktu_selesai.strftime("%H:%M")

def format_rupiah(nominal):
    return f"Rp {int(nominal):,}".replace(",", ".")

def format_rupiah_input(key):
    txt = st.session_state.get(key, "")
    digits = "".join([c for c in txt if c.isdigit()])
    st.session_state[key] = "{:,}".format(int(digits)).replace(",", ".") if digits else ""

def tampilkan_rate(rate):
    return f"{(1 - rate) * 100:.1f}%"

def hitung_fee(jenis, nominal, rate):
    if jenis == "Gesek Kotor":
        return int(nominal * (1 - rate))
    else:
        return int(nominal / rate - nominal)

def hitung_pembagian_edc_prioritas(total_transaksi, mesin_edc):
    sisa = total_transaksi
    pembagian = []
    mesin_edc.sort(key=lambda x: x['prioritas'])
    for mesin in mesin_edc:
        ambil = min(sisa, mesin['batas'])
        pembagian.append((mesin['nama'], ambil))
        sisa -= ambil
        if sisa <= 0:
            break
    return pembagian, sisa

def fmt_rp(val):
    return f"Rp. {int(val):,}".replace(",", ".")

RNG = random.SystemRandom()
SAFETY_GAP = 1_000

def rp(x: int) -> str:
    """Rupiah formatter: 1000000 -> 'Rp1,000,000'"""
    return f"Rp{x:,}"

def _is_non_round(val: int) -> bool:
    return val % 1000 != 0

def _rand_adjust(val: int, low: int = 237, high: int = 937) -> int:
    if _is_non_round(val):
        return 0
    high = min(high, max(low + 1, val - 1))
    return RNG.randrange(low, high)

def split_transaction_exact(total: int, machines: List[Tuple[str, int]], max_swipes: int = 2) -> List[Dict]:
    """Split *total* across *machines*, keeping NOMINAL < limit-SAFETY_GAP,
    non-round, max *max_swipes* per machine, and guaranteeing exact total.
    Returns list of dict {'machine': str, 'amount': int}.
    """
    machines = sorted(machines, key=lambda x: -x[1])
    counts = {m: 0 for m, _ in machines}
    remaining = total
    parts: List[Dict] = []

    while remaining > 0:
        progressed = False
        for name, limit in machines:
            if counts[name] < max_swipes and remaining <= limit - SAFETY_GAP:
                amt = remaining - _rand_adjust(remaining)
                if amt == 0:
                    amt = remaining - 777
                parts.append({"machine": name, "amount": amt})
                counts[name] += 1
                remaining -= amt
                progressed = True
                break
        if remaining == 0:
            break
        if progressed:
            continue
        for name, limit in machines:
            if counts[name] >= max_swipes:
                continue
            base = min(limit - SAFETY_GAP, remaining)
            amt = base - _rand_adjust(base)
            amt = max(500, amt)
            parts.append({"machine": name, "amount": amt})
            counts[name] += 1
            remaining -= amt
            progressed = True
            if remaining <= 0:
                break
        if not progressed:
            raise RuntimeError("Unable to allocate remaining amount with given limits/swipes.")

    current_total = sum(p["amount"] for p in parts)
    diff = total - current_total

    if diff != 0:
        for p in parts:
            limit = dict(machines)[p["machine"]]
            headroom = (limit - SAFETY_GAP) - p["amount"]
            if 0 < diff <= headroom and _is_non_round(p["amount"] + diff):
                p["amount"] += diff
                diff = 0
                break
            if diff < 0 and abs(diff) < p["amount"] - 500 and _is_non_round(p["amount"] + diff):
                p["amount"] += diff
                diff = 0
                break
        if diff != 0:
            for p in parts:
                if diff == 0:
                    break
                limit = dict(machines)[p["machine"]]
                headroom = (limit - SAFETY_GAP) - p["amount"]
                step = diff if abs(diff) <= headroom else headroom
                if step == 0:
                    continue
                if _is_non_round(p["amount"] + step):
                    p["amount"] += step
                    diff -= step
            if diff != 0:
                parts[-1]["amount"] += diff
                diff = 0

    assert sum(p["amount"] for p in parts) == total, "Total mismatch after adjustment!"
    return parts

def menu_pembagian_edc():
    st.header("🧮 Proporsional Transaksi Besar")

    total_transaksi = st.number_input(
        "Masukkan Total Transaksi (Rp)", min_value=50_000_000, step=10_000_000, format="%d"
    )
    max_swipes = st.number_input(
        "Maksimum Gesek per Mesin", min_value=1, max_value=5, value=2
    )
    jumlah_mesin = st.number_input(
        "Masukkan Jumlah Mesin EDC", min_value=1, max_value=20, value=3, step=1
    )

    st.subheader("Detail Setiap Mesin EDC")
    mesin_edc_input = []
    for i in range(int(jumlah_mesin)):
        col1, col2 = st.columns([3, 2])
        with col1:
            nama = st.text_input(f"Nama Mesin EDC {i+1}", value=f"EDC {i+1}", key=f"nama_{i}")
        with col2:
            batas = st.number_input(
                f"Batas Maks per Swipe (Rp)", min_value=10_000_000, step=10_000_000, key=f"batas_{i}"
            )
        mesin_edc_input.append((nama, int(batas)))

    if st.button("Hitung Pembagian") and total_transaksi > 0:
        try:
            plan = split_transaction_exact(int(total_transaksi), mesin_edc_input, int(max_swipes))
        except RuntimeError as e:
            st.error(str(e))
        else:
            df = pd.DataFrame(plan)
            df["amount"] = df["amount"].apply(rp)
            st.success("### Rincian Pembagian")
            st.dataframe(df, use_container_width=True)
            st.markdown(f"**TOTAL:** {rp(sum(p['amount'] for p in plan))}")
            st.download_button(
                "📥 Download CSV", df.to_csv(index=False).encode(), "split_plan.csv", "text/csv"
            )
menu = st.sidebar.selectbox("Pilih Menu", [
    "Konven",
    "Input Data",
    "Marketplace",
    "Countdown",
    "Proporsional",
])

# ===============================
# MENU 1: Konvensional 
# ===============================
if menu == "Konven":
    st.header("💰 Perbandingan Gesek")
    
    if "nominal_input" not in st.session_state:
        st.session_state.nominal_input = ""

    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        tipe_rate = st.selectbox("Tipe Rate Jual:", ["Persentase (%)", "Nominal (Rp)"], key="menu1_tipe_rate")
    with row1_col2:
        if tipe_rate == "Persentase (%)":
            preset_opts = ["Custom",  "2.0%", "2.3%", "2.4%", "2.5%", "2.6%", "3.3%", "3.5%", "4.0%", "4.7%",  "5.0%", "7.0%", "8.0%", "14.0%"]
            preset = st.selectbox("Pilih Persentase:", preset_opts, key="menu1_preset")
        else:
            st.write("") 

    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        if tipe_rate == "Persentase (%)":
            if preset != "Custom":
                rt_percent = float(preset.replace("%", ""))
            else:
                rt_percent = st.number_input("Input Rate (%)", 0.0, 99.0, 2.5, 0.1, format="%.2f")
            rate_decimal = rt_percent / 100.0
            rt_str = f"{rt_percent:.2f}%"
        else:
            nominal_rate = st.number_input("Rate (Rp)", min_value=0, step=1000)
            rate_decimal = None
            rt_str = format_rupiah(nominal_rate)

    with row2_col2:
        SVCS = [
            {"label_ui": "Normal (3 Jam)", "cost": 0, "normalized": "Normal"},
            {"label_ui": f"Express Non Member — {fmt_rp(18_000)}", "cost": 18_000, "normalized": "Express Non Member"},
            {"label_ui": f"Express Member — {fmt_rp(15_000)}", "cost": 15_000, "normalized": "Express Member"},
        ]
        layanan_transfer_ui = st.selectbox("Layanan Transfer:", [s["label_ui"] for s in SVCS])
        svc = next(s for s in SVCS if s["label_ui"] == layanan_transfer_ui)

    st.markdown("---")
    BIAYA_TAMBAHAN_LIST = {
        "Biaya Transaksi di Mesin EDC": 2_000,
        "Biaya QRIS By Whatsapp": 3_000,
        "Biaya Administrasi Nasabah Baru": 10_000,
        "Biaya Transfer Beda Bank": 10_000,
        "Biaya Layanan Link Toko Tokopedia": 10_000,
        "Biaya Layanan Express Tokopedia": 30_000,
        "Biaya Layanan Express Shopee": 30_000,
    }
    biaya_pilihan = st.multiselect("➕ Tambahkan Biaya Tambahan (Opsional):", list(BIAYA_TAMBAHAN_LIST.keys()))
    
    biaya_tambahan_nominal = sum(BIAYA_TAMBAHAN_LIST[b] for b in biaya_pilihan)
    biaya_total = biaya_tambahan_nominal + svc["cost"]
    
    st.text_input(
        label="💵 Masukkan Nominal Transaksi (Rp):",
        key="nominal_input",
        on_change=format_rupiah_input,
        args=("nominal_input",),
        placeholder="Ketik angka..."
    )

    raw_val = st.session_state.nominal_input.replace(".", "")
    nominal_int = int(raw_val) if raw_val.isdigit() else 0

    if nominal_int > 0:
        EXTRA_FEE_BERSIH = 1 
        waktu_sekarang = datetime.now(ZoneInfo("Asia/Jakarta"))
        durasi = timedelta(minutes=30) if svc["normalized"] == "Express" else timedelta(hours=3)
        est_selesai = estimasi_selesai(waktu_sekarang, durasi)
        
        if tipe_rate == "Persentase (%)":
            k_fee = int(round(nominal_int * rate_decimal))
            k_terima = nominal_int - k_fee - biaya_total
            b_transaksi = int(((nominal_int + biaya_total) / (1 - rate_decimal)) + EXTRA_FEE_BERSIH)
        else:
            k_terima = nominal_int - nominal_rate - biaya_total
            b_transaksi = int(nominal_int + biaya_total + nominal_rate + EXTRA_FEE_BERSIH)

        res_col1, res_col2 = st.columns(2)
        
        with res_col1:
            total_potongan_kotor = k_fee + biaya_total
            st.markdown(f"""
            <div style="background:#fff4f4; border:1px solid #feb2b2; padding:20px; border-radius:15px; text-align:center;">
                <p style="color:#c53030; margin:0; font-size:0.9rem; font-weight:bold;">METODE GESEK KOTOR</p>
                <h2 style="margin:10px 0; color:#c53030;">{format_rupiah(max(0, k_terima))}</h2>
                <p style="color:#e53e3e; margin:0; font-size:0.85rem;">Potongan: {format_rupiah(total_potongan_kotor)}</p>
                <small style="color:#718096;">Dana yang Anda Terima</small>
            </div>
            """, unsafe_allow_html=True)

        with res_col2:
            total_biaya_bersih = b_transaksi - nominal_int
            st.markdown(f"""
            <div style="background:#f0fff4; border:1px solid #9ae6b4; padding:20px; border-radius:15px; text-align:center;">
                <p style="color:#2f855a; margin:0; font-size:0.9rem; font-weight:bold;">METODE GESEK BERSIH</p>
                <h2 style="margin:10px 0; color:#2f855a;">{format_rupiah(b_transaksi)}</h2>
                <p style="color:#38a169; margin:0; font-size:0.85rem;">Total Fee: {format_rupiah(total_biaya_bersih)}</p>
                <small style="color:#718096;">Nominal Harus Digesek</small>
            </div>
            """, unsafe_allow_html=True)

        with st.expander("🔍 Lihat Rincian Biaya Tambahan", expanded=True):
            rincian_data = []
            if svc["cost"] > 0:
                rincian_data.append({"Komponen": "Layanan Transfer", "Biaya": format_rupiah(svc["cost"])})
            for b in biaya_pilihan:
                rincian_data.append({"Komponen": b, "Biaya": format_rupiah(BIAYA_TAMBAHAN_LIST[b])})
            
            if rincian_data:
                df_rincian = pd.DataFrame(rincian_data)
                st.table(df_rincian)
                st.markdown(f"**Total Potongan Tambahan: {format_rupiah(biaya_total)}**")
            else:
                st.write("Tidak ada biaya tambahan selain rate jasa.")

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.warning(f"✅ **Waktu Pembelian:** {waktu_sekarang.strftime('%H:%M')} WIB")
        with c2:
            st.success(f"✅ **Dana Masuk:** {est_selesai} WIB")
            
    else:
        st.info("💡 Masukkan nominal untuk melihat perbandingan secara real-time.")

# =============================================
# MENU 2: INPUT DATA TRANSAKSI
# =============================================
elif menu == "Input Data":
    import math
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    def format_rupiah(angka):
        return f"Rp {int(round(angka)):,}".replace(",", ".")

    st.title("Form Input Data Transaksi")

    SVCS = [
        {"label_ui": "Normal 3 Jam", "cost": 0.0},
        {"label_ui": "Express Member — Rp. 15.000", "cost": 15000.0},
        {"label_ui": "Express Non Member — Rp. 18.000", "cost": 18000.0},
    ]
    SVC_BY_LABEL = {s["label_ui"]: s for s in SVCS}

    st.subheader("🧾 Data Transaksi Utama")
    col_h1, col_h2, col_h3 = st.columns(3)
    with col_h1:
        transaksi_no = st.number_input("No. Transaksi", min_value=1, step=1, format="%d")
    with col_h2:
        metode_transaksi = st.selectbox("Metode Transaksi", ["Konven", "Online"])
    with col_h3:
        lay = st.selectbox("Jenis Layanan", [s["label_ui"] for s in SVCS])
    
    svc = SVC_BY_LABEL[lay]

    # =============================================
    # MODE 1: EXPRESS
    # =============================================
    if "Express" in lay:
        st.info("⚡ **Mode: Express Aktif**")
        with st.form(key="form_express_sync_fixed"):
            c1, c2, c3 = st.columns(3)
            nama = c1.text_input("Nama Nasabah")
            kategori = c2.selectbox("Kategori Nasabah", ["Langganan", "Baru"])
            kelas = c3.selectbox("Kelas Nasabah", ["Non Member", "Gold", "Platinum", "Prioritas", "Silver"])

            m1, m2, m3 = st.columns([2, 2, 1])
            metode_gesek = m1.selectbox("Metode Perhitungan", ["Gesek Kotor", "Gesek Bersih"])
            fee_type = m2.selectbox("Jenis Fee", ["Persentase (%)", "Flat (Rp)"])
            
            if fee_type == "Persentase (%)":
                fee_persen = m3.number_input("Fee (%)", min_value=0.0, step=0.1, format="%.2f", value=0.0)
                fee_decimal = fee_persen / 100.0
            else:
                fee_flat = m3.number_input("Fee Flat (Rp)", min_value=0.0, step=1000.0, value=0.0)
                fee_decimal = 0.0

            st.markdown("### 💰 Biaya Tambahan")
            b1, b2, b3 = st.columns(3)
            b_trf = b1.number_input("B. Transfer Non-BCA", min_value=0.0, step=2500.0, value=0.0)
            b_edc = b2.number_input("B. Transaksi Mesin EDC", min_value=0.0, step=2000.0, value=0.0)
            b_qris = b3.number_input("B. QRIS By WA", min_value=0.0, step=3000.0, value=0.0)
            
            label_input = "Jumlah Transaksi (Gesek)" if metode_gesek == "Gesek Kotor" else "Jumlah Transfer (Terima)"
            input_nominal = st.number_input(label_input, min_value=0.0, step=50000.0, value=0.0)

            submit_express = st.form_submit_button("Generate WhatsApp Express")
            
        if submit_express:
            biaya_baru = 10000.0 if kategori == "Baru" else 0.0
            total_biaya = b_trf + b_edc + b_qris + biaya_baru + svc["cost"]

            if metode_gesek == "Gesek Kotor":
                jt_final = input_nominal
                fee_jasa = round(jt_final * fee_decimal) if fee_type == "Persentase (%)" else fee_flat
                trf_final = jt_final - fee_jasa - total_biaya
            else:
                if fee_type == "Persentase (%)":
                    jt_final = math.ceil((input_nominal + total_biaya) / (1.0 - fee_decimal))
                else:
                    jt_final = input_nominal + total_biaya + fee_flat
                trf_final = input_nominal

            waktu_selesai = (datetime.now(ZoneInfo("Asia/Jakarta")) + timedelta(minutes=20)).strftime("%H:%M WIB")
            rate_tampil = f"{fee_persen:.2f}%" if fee_type == "Persentase (%)" else format_rupiah(fee_flat)
            
            teks_express = f"""*TRANSAKSI NO. {transaksi_no} ({metode_transaksi.upper()})*
*EXPRESS*

• Nama Nasabah : *{nama}*
• Kategori Nasabah : *{kategori}*
• Kelas Nasabah : *{kelas}*
• Rate Jual : *{rate_tampil}*
• Jumlah Transfer : *{format_rupiah(trf_final)}*
_______________________________
Estimasi Selesai: {waktu_selesai}"""
            st.code(teks_express, language="text")

    # =============================================
    # MODE 2: NORMAL 3 JAM
    # =============================================
    else:
        st.markdown("### 🕓 Mode: Normal 3 Jam")
        tab1, tab2, tab3 = st.tabs(["🧍 Data Nasabah", "💳 Detail Transaksi", "💰 Biaya & Hasil"])

        with tab1:
            c1, c2, c3 = st.columns(3)
            nama_n = c1.text_input("Nama Nasabah", key="n_norm")
            jenis_n = c2.selectbox("Kategori Nasabah", ["Langganan", "Baru"], key="k_norm")
            kelas_n = c3.selectbox("Kelas Nasabah", ["Non Member", "Gold", "Platinum", "Prioritas", "Silver"], key="kls_norm")

        with tab2:
            media = st.selectbox("Jenis Media Pencairan", [
                "Mesin EDC - BNI Blurry Fashion Store", "Mesin EDC - BRI Abadi Cell Sersan", 
                "Mesin EDC - BCA Abadi Fashion Malang", "QRIS Statis - BNI Indah Mebeul", "Paper Id - Kreasi Mode", "Lainnya"
            ])
            produk = st.text_input("Produk", placeholder="Contoh: Kartu Kredit - BANK BNI")
            
            r1, r2, r3 = st.columns([2, 1, 1])
            rt_type = r1.radio("Tipe Rate Jual", ["Persentase (%)", "Nominal (Rp)"], horizontal=True)
            if rt_type == "Persentase (%)":
                rt_val = r2.number_input("Rate Jual (%)", min_value=0.0, step=0.1, format="%.2f", value=0.0)
                rate_decimal = rt_val / 100.0
                rt_str = f"{rt_val:.2f}%"
            else:
                rt_nom = r2.number_input("Rate Jual (Rp)", min_value=0.0, step=1000.0, value=0.0)
                rate_decimal = 0.0
                rt_str = format_rupiah(rt_nom)
            
            mdr_percent = r3.number_input("Rate MDR (%)", min_value=0.0, step=0.1, format="%.2f", value=0.0)

        with tab3:
            m_gestun = st.radio("Metode Gestun", ["Kotor", "Bersih"], horizontal=True)
            b1, b2, b3 = st.columns(3)
            biaya_transfer = b1.number_input("Biaya Transfer Selain BCA", min_value=0.0, step=2500.0, value=0.0)
            biaya_edc = b2.number_input("Biaya Transaksi EDC", min_value=0.0, step=2000.0, value=0.0)
            biaya_qris = b3.number_input("Biaya QRIS By WA", min_value=0.0, step=3000.0, value=0.0)
            
            biaya_baru_n = 10000.0 if jenis_n == "Baru" else 0.0
            total_biaya_n = biaya_transfer + biaya_edc + biaya_qris + biaya_baru_n

            if m_gestun == "Kotor":
                input_jt = st.number_input("Jumlah Transaksi (Rp)", min_value=0.0, step=100000.0, value=0.0)
                fee_jasa_n = round(input_jt * rate_decimal) if rt_type == "Persentase (%)" else rt_nom
                jt_final_n = input_jt
                trf_final_n = jt_final_n - fee_jasa_n - total_biaya_n
            else:
                input_trf = st.number_input("Jumlah Transfer (Rp)", min_value=0.0, step=100000.0, value=0.0)
                if rt_type == "Persentase (%)":
                    jt_final_n = math.ceil((input_trf + total_biaya_n) / (1.0 - rate_decimal))
                else:
                    jt_final_n = input_trf + total_biaya_n + rt_nom
                trf_final_n = input_trf

            st.divider()
            p1, p2 = st.columns(2)
            petugas_nama = p1.text_input("Nama Petugas", value="Thoriq")
            petugas_shift = p2.selectbox("Shift Kerja", ["1 Shift", "Shift Pagi", "Shift Siang", "Shift Malam"])

            if st.button("Generate WhatsApp Normal"):
                waktu_selesai_n = (datetime.now(ZoneInfo("Asia/Jakarta")) + timedelta(hours=3)).strftime("%H:%M WIB")
                
                if rt_type == "Persentase (%)":
                    ru_str = f"{(rt_val - mdr_percent):.2f}%"
                else:
                    mdr_rp = jt_final_n * (mdr_percent / 100.0)
                    ru_str = format_rupiah(rt_nom - mdr_rp)

                teks_normal = f"""*TRANSAKSI NO. {transaksi_no} ({metode_transaksi.upper()})*
_______________________________
• Nama Nasabah : {nama_n}
• Kategori Nasabah : {jenis_n} ({kelas_n})
• Jenis Media Pencairan : {media}
• Produk : {produk}
• Rate Jual : {rt_str}
• Rate Untung : {ru_str}
• Nominal Transaksi : *{format_rupiah(jt_final_n)}*
• Biaya Nasabah Baru : Rp. {int(biaya_baru_n):,}
• Biaya Transfer Selain BCA : Rp. {int(biaya_transfer):,}
• Biaya Transaksi di Mesin EDC : Rp. {int(biaya_edc):,}
• Biaya Layanan QRIS By WhatsApp : Rp. {int(biaya_qris):,}
_______________________________
Jumlah Transfer : *{format_rupiah(trf_final_n)}*
🕓 Estimasi Selesai: {waktu_selesai_n}

Petugas: {petugas_nama} ({petugas_shift})"""
                st.code(teks_normal, language="text")

# =============================================
# Menu 3: Marketplace
# =============================================
elif menu == "Marketplace":
    st.title("🛒 Estimasi Pencairan Marketplace")
    st.markdown("""
    Masukkan data berikut untuk menghitung **estimasi pencairan setelah semua biaya** marketplace dan gestun.
    💡 **Komponen biaya yang digunakan dalam perhitungan ini:**
    - **Fee Merchant**: potongan dari marketplace (8%–14%) *(bisa dikosongkan)*
    - **Fee Gestun**: potongan jasa pencairan (1%–10%)
    - **Biaya Toko Tokopedia**: Rp 10.000 *(hanya untuk Tokopedia)*
    - **Biaya Super Kilat**: Rp 30.000 *(opsional)*
    - **Biaya Admin Nasabah Baru**: Rp 10.000 *(opsional)*
    - **Biaya Transfer Non-BCA**: Rp 10.000 *(opsional)*
    """)
    nominal_checkout_str = st.text_input(
        label="Masukkan Nominal Checkout Produk (Rp):",
        key="nominal_marketplace",
    )
    def to_int(value):
        try:
            return int(value.replace("Rp", "").replace(".", "").replace(",", "").strip())
        except:
            return 0
    nominal_checkout_int = to_int(nominal_checkout_str)
    marketplace = st.selectbox("Pilih Marketplace", ["Tokopedia", "Shopee"])
    # --- Fee merchant (opsional) ---
    fee_merchant = st.selectbox(
        "Fee Merchant (%)",
        ["Tidak Ada", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
        index=0
    )
    fee_gestun = st.selectbox("Fee Gestun (%)", ["Tidak Ada", 8, 9, 10, 11, 12, 13, 14],
        index=0
    )
    st.markdown("### ✅ Biaya Tambahan (Checklist sesuai kondisi aktual)")
    biaya_admin_nasabah_baru = st.checkbox("Biaya Administrasi Nasabah Baru (Rp 10.000)", value=False)
    biaya_transfer_non_bca = st.checkbox("Biaya Transfer Selain Bank BCA (Rp 10.000)", value=False)
    biaya_toko = st.checkbox("Biaya Toko Tokopedia (Rp 10.000)", value=(marketplace == "Tokopedia"))
    biaya_super_kilat_tokopedia = st.checkbox("Biaya Layanan Super Kilat Tokopedia (Rp 30.000)", value=False)
    biaya_super_kilat_shopee = st.checkbox("Biaya Layanan Super Kilat Shopee (Rp 30.000)", value=False)
    total_biaya_tambahan = 0
    biaya_detail = []
    if biaya_admin_nasabah_baru:
        total_biaya_tambahan += 10_000
        biaya_detail.append(("Biaya Admin Nasabah Baru", 10_000))
    if biaya_transfer_non_bca:
        total_biaya_tambahan += 10_000
        biaya_detail.append(("Biaya Transfer Non-BCA", 10_000))
    if biaya_toko:
        total_biaya_tambahan += 10_000
        biaya_detail.append(("Biaya Toko Tokopedia", 10_000))
    if biaya_super_kilat_tokopedia:
        total_biaya_tambahan += 30_000
        biaya_detail.append(("Biaya Super Kilat Tokopedia", 30_000))
    if biaya_super_kilat_shopee:
        total_biaya_tambahan += 30_000
        biaya_detail.append(("Biaya Super Kilat Shopee", 30_000))
    if st.button("Hitung Estimasi", disabled=(nominal_checkout_int <= 0)):
        waktu_mulai = datetime.now(ZoneInfo("Asia/Jakarta"))
        fee_merchant_rp = 0 if fee_merchant == "Tidak Ada" else nominal_checkout_int * (fee_merchant / 100)
        fee_gestun_rp = nominal_checkout_int * (fee_gestun / 100)
        if fee_merchant != "Tidak Ada":
            biaya_detail.insert(0, (f"Fee Merchant ({fee_merchant}%)", fee_merchant_rp))
        else:
            biaya_detail.insert(0, ("Fee Merchant (Tidak Ada)", 0))
        biaya_detail.insert(1, (f"Fee Gestun ({fee_gestun}%)", fee_gestun_rp))
        total_biaya = fee_merchant_rp + fee_gestun_rp + total_biaya_tambahan
        nominal_diterima = nominal_checkout_int - total_biaya
        st.subheader("📊 Hasil Estimasi Pencairan")
        st.write(f"**Waktu Perhitungan:** {waktu_mulai.strftime('%d %B %Y, %H:%M:%S')} WIB")
        st.write(f"**Marketplace:** {marketplace}")
        st.write(f"**Nominal Checkout Produk:** Rp {nominal_checkout_int:,.0f}".replace(",", "."))
        st.markdown("#### 🧾 Rincian Biaya")
        df_biaya = pd.DataFrame(biaya_detail, columns=["Jenis Biaya", "Nominal (Rp)"])
        df_biaya["Nominal (Rp)"] = df_biaya["Nominal (Rp)"].apply(lambda x: f"Rp {x:,.0f}".replace(",", "."))
        st.table(df_biaya)
        st.markdown("---")
        st.success(f"💸 **Estimasi Dana Diterima: Rp {nominal_diterima:,.0f}**".replace(",", "."))

# =============================================
# MENU 5: Pembagian Transaksi EDC
# =============================================
elif menu == "Proporsional":
    menu_pembagian_edc()
# =============================================
# MENU 4: Countdown
# =============================================
elif menu == "Countdown":
    st.title("⏱️ Hitung Selisih Waktu Antar Jam")
    if "start_time" not in st.session_state:
        st.session_state.start_time = datetime.now(ZoneInfo("Asia/Jakarta")).time()
    if "end_time" not in st.session_state:
        st.session_state.end_time = datetime.now(ZoneInfo("Asia/Jakarta")).time()
    start_time = st.time_input("Waktu Mulai", key="start_time")
    end_time   = st.time_input("Waktu Selesai", key="end_time")
    if st.button("Hitung Selisih"):
        today = datetime.now(ZoneInfo("Asia/Jakarta")).date()
        t1 = datetime.combine(today, start_time)
        t2 = datetime.combine(today, end_time)
        if t2 < t1:
            t2 += timedelta(days=1)
        delta = t2 - t1
        jam, sisa = divmod(delta.seconds, 3600)
        menit, detik = divmod(sisa, 60)
        st.success(f"Waktu yang berlalu: {jam} jam {menit} menit {detik} detik")