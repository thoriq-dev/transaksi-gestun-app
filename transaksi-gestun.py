from __future__ import annotations

import streamlit as st
# --- App Config ---
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

# Simpan original SEKALI di level modul (bukan session_state)
_ORIG_ST_WRITE = st.write
_ORIG_ST_HELP  = st.help

def _noop(*args, **kwargs):
    return

def _safe_write(*args, **kwargs):
    # Saring callable saat debug OFF agar kotak "function … No docs available" tidak muncul
    if not st.session_state.get("debug_help", False):
        args = [a for a in args if not callable(a)]
        kwargs = {k: v for k, v in kwargs.items() if not callable(v)}
        if not args and not kwargs:
            return
    return _ORIG_ST_WRITE(*args, **kwargs)

def apply_dev_shield():
    if st.session_state.get("debug_help", False):
        # Debug ON → pulihkan API asli
        st.write = _ORIG_ST_WRITE
        st.help  = _ORIG_ST_HELP
    else:
        # Debug OFF → aktifkan filter
        st.write = _safe_write
        st.help  = _noop

apply_dev_shield()
# ===== End Dev Shield (GLOBAL) =====


# --- Fungsi Pendukung ---
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
    return f"{int((1 - rate) * 1000) / 10}%"

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

# Helper: format Rupiah without decimals and with dot as thousand separator
def fmt_rp(val):
    return f"Rp. {int(val):,}".replace(",", ".")

# Helper: For Random split_transaction_exact 
RNG = random.SystemRandom()
SAFETY_GAP = 1_000  # stay below hard limit by Rp1.000

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

# Core algorithm: split_transaction_exact
# ----------------------------------------------------------------------------------
def split_transaction_exact(total: int, machines: List[Tuple[str, int]], max_swipes: int = 2) -> List[Dict]:
    """Split *total* across *machines*, keeping NOMINAL < limit-SAFETY_GAP,
    non-round, max *max_swipes* per machine, and guaranteeing exact total.
    Returns list of dict {'machine': str, 'amount': int}.
    """
    machines = sorted(machines, key=lambda x: -x[1])  # largest limit first
    counts = {m: 0 for m, _ in machines}
    remaining = total
    parts: List[Dict] = []

    # Greedy allocation
    while remaining > 0:
        progressed = False
        # 1. If remaining fits one machine
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
        # 2. Normal slice
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

    # Exact-total adjustment
    current_total = sum(p["amount"] for p in parts)
    diff = total - current_total

    if diff != 0:
        # Try single placement
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
        # Split diff if needed
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
    "Hitung Nominal Transaksi",
    "Input Data Transaksi",
    "Jam",
    "Proporsional Transaksi Besar",
])

# ===============================
# MENU 1: HITUNG NOMINAL TRANSAKSI (rapih, tanpa Keterangan Layanan)
# ===============================
if menu == "Hitung Nominal Transaksi":
    st.header("💰 Hitung Nominal Transaksi")

    # Pilihan jenis perhitungan
    jenis = st.selectbox("Pilih Jenis Perhitungan:", ["Gesek Kotor", "Gesek Bersih"])

    # Pilihan tipe rate jual
    tipe_rate = st.selectbox(
        "Tipe Rate Jual:",
        ["Persentase (%)", "Nominal (Rp)"],
        key="menu1_tipe_rate"
    )

    # Jika persentase: pilih preset atau custom
    if tipe_rate == "Persentase (%)":
        preset_opts = ["Custom", "2.5%", "2.6%", "3.5%", "4.7%"]
        preset = st.selectbox("Pilih Persentase:", preset_opts, key="menu1_preset")

        if preset != "Custom":
            rt_percent = float(preset.replace("%", ""))
        else:
            rt_percent = st.number_input(
                "Rate Jual (%) (custom):",
                min_value=0.0,
                max_value=100.0,
                step=0.1,
                format="%.2f",
                key="menu1_rt_percent"
            )

        # Guard agar tidak 100% (menghindari divisi nol di Gesek Bersih)
        if rt_percent >= 100.0:
            st.error("Rate tidak boleh 100% atau lebih.")
            st.stop()

        rate_decimal = rt_percent / 100.0
        nominal_rate = 0
        rt_str = f"{rt_percent:.2f}%"

    # Jika nominal tetap
    else:
        nominal_rate = st.number_input(
            "Rate Jual (Rp):",
            min_value=0,
            step=1000,
            format="%d",
            key="menu1_rt_nominal"
        )
        rate_decimal = None
        rt_str = f"Rp {nominal_rate:,}".replace(",", ".")

    # ---------------- Konfigurasi biaya tambahan & layanan transfer ----------------
    # Biaya lain (bukan layanan)
    BIAYA_TAMBAHAN = {
        "Biaya administrasi nasabah baru": 10_000,
        "Biaya transfer beda bank": 10_000,
        "Biaya transaksi di mesin edc": 2_000,
    }

    # Layanan transfer dengan label UI berisi harga + tipe dinormalisasi untuk estimasi durasi
    SVCS = [
        {
            "label_ui": "Normal",
            "label_biaya": "Layanan normal",
            "cost": 0,
            "normalized": "Normal",
        },
        {
            "label_ui": f"Kilat Member | Non Member — {fmt_rp(15_000)}",
            "label_biaya": "Biaya layanan kilat",
            "cost": 15_000,
            "normalized": "Kilat",
        },
        {
            "label_ui": f"Super Kilat Member — {fmt_rp(15_000)}",
            "label_biaya": "Biaya layanan super kilat (member)",
            "cost": 15_000,
            "normalized": "Super Kilat",
        },
        {
            "label_ui": f"Super Kilat Non Member — {fmt_rp(18_000)}",
            "label_biaya": "Biaya layanan super kilat (non member)",
            "cost": 18_000,
            "normalized": "Super Kilat",
        },
    ]
    # Map label → svc
    SVC_BY_LABEL = {s["label_ui"]: s for s in SVCS}

    layanan_transfer_ui = st.selectbox(
        "Pilih Layanan Transfer:",
        [s["label_ui"] for s in SVCS],
        key="menu1_layanan_transfer"
    )
    svc = SVC_BY_LABEL[layanan_transfer_ui]

    # Biaya tambahan lain (non-layanan)
    biaya_pilihan = st.multiselect(
        "Pilih Biaya Tambahan Lainnya:",
        list(BIAYA_TAMBAHAN.keys()),
        key="menu1_biaya_pilihan"
    )

    # Hitung biaya tambahan total (biaya lain + biaya layanan)
    biaya_total = sum(BIAYA_TAMBAHAN[b] for b in biaya_pilihan) + svc["cost"]
    st.write(f"▶️ Total Biaya Tambahan: {format_rupiah(biaya_total)}")

    # -------- Ringkasan biaya tambahan (breakdown) --------
    breakdown_rows = [
        {"Komponen": b, "Nominal": format_rupiah(BIAYA_TAMBAHAN[b])}
        for b in biaya_pilihan
    ]
    if svc["cost"] > 0:
        breakdown_rows.append({"Komponen": svc["label_biaya"], "Nominal": format_rupiah(svc["cost"])})
    # ------------------------------------------------------

    # Callback format rupiah untuk text_input
    def format_rupiah_input(key):
        txt = st.session_state.get(key, "")
        digits = "".join([c for c in txt if c.isdigit()])
        st.session_state[key] = "{:,}".format(int(digits)).replace(",", ".") if digits else ""

    if "nominal_input" not in st.session_state:
        st.session_state.nominal_input = ""

    st.text_input(
        label=f"Masukkan nominal {'Transaksi (Gesek Kotor)' if jenis == 'Gesek Kotor' else 'Transfer Diterima (Gesek Bersih)'} (Rp):",
        key="nominal_input",
        on_change=format_rupiah_input,
        args=("nominal_input",),
    )

    raw = st.session_state.nominal_input.replace(".", "")
    nominal_int = int(raw) if raw.isdigit() else 0

    # ====== CSS minimal untuk kartu ======
    st.markdown("""
        <style>
        .card-grid {display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 10px 0 0 0;}
        .card {border: 1px solid #e8e8e8; border-radius: 14px; padding: 14px 16px;}
        .card h4 {margin: 0 0 8px 0; font-size: 1.0rem; color: #6b7280;}
        .card p {margin: 0; font-weight: 700; font-size: 1.25rem;}
        .pill {display:inline-block; padding:4px 10px; border-radius:9999px; background:#f3f4f6; font-size:0.9rem;}
        .section-title {font-size:1.15rem; font-weight:700; margin: 12px 0 6px 0;}
        </style>
    """, unsafe_allow_html=True)
    # =====================================

    # Hitung & tampilkan hasil
if st.button("Hitung Sekarang", disabled=(nominal_int <= 0)):
    waktu_mulai = datetime.now(ZoneInfo("Asia/Jakarta"))
    # gunakan tipe layanan yang dinormalisasi untuk estimasi durasi
    estimasi_selesai_transfer = estimasi_selesai(waktu_mulai, estimasi_durasi(svc["normalized"]))

    # Perhitungan nominal (pakai round lalu int)
    if jenis == "Gesek Kotor":
        if tipe_rate == "Persentase (%)":
            fee_rupiah = int(round(nominal_int * rate_decimal))
            nominal_transfer = int(round(nominal_int * (1 - rate_decimal))) - biaya_total
        else:
            fee_rupiah = nominal_rate
            nominal_transfer = nominal_int - nominal_rate - biaya_total
        nominal_transfer = max(0, nominal_transfer)
        nominal_transaksi = nominal_int

    else:  # Gesek Bersih
        if tipe_rate == "Persentase (%)":
            fee_rupiah = int(round(nominal_int / (1 - rate_decimal) - nominal_int))
            fee = fee_rupiah
        else:
            fee_rupiah = nominal_rate
            fee = nominal_rate
        nominal_transaksi = nominal_int + fee + biaya_total
        nominal_transfer = nominal_int

    # ==============================
    # Hitung nilai fee dalam Rupiah & teks penjelasan
    # ==============================
    if tipe_rate == "Persentase (%)":
        if jenis == "Gesek Kotor":
            # Gesek Kotor: fee dihitung langsung dari nominal transaksi
            fee_rupiah = int(round(nominal_int * rate_decimal))
            fee_info = (
                f"💡 Fee {rt_str} dari {format_rupiah(nominal_int)} "
                f"adalah {format_rupiah(fee_rupiah)}"
            )

        elif jenis == "Gesek Bersih":
            # Gesek Bersih: cari transaksi kotor & fee dengan rumus terbalik
            transaksi_kotor = nominal_int / (1 - rate_decimal)
            fee_rupiah = int(round(transaksi_kotor - nominal_int))
            fee_info = (
                f"💡 Fee {rt_str} dari {format_rupiah(nominal_int)} (bersih) "
                f"adalah {format_rupiah(fee_rupiah)} "
            )

    else:
        # Jika tipe rate nominal (Rp), tampilkan langsung tanpa rumus persentase
        fee_rupiah = nominal_rate
        fee_info = (
            f"💡 Fee tetap sebesar {format_rupiah(fee_rupiah)} "
            f"berdasarkan nilai rate nominal."
        )

    # ==============================
    # Tampilkan hasil
    # ==============================
    st.markdown("<h2 style='text-align:center;'>📊 Hasil Perhitungan</h2>", unsafe_allow_html=True)
    st.caption(f"{fee_info}")

    # Ringkasan input (jenis & rate) sebagai pill
    colA, colB, colC = st.columns([1,1,1])
    with colA:
        st.markdown(f"<span class='pill'>Rate: <b>{rt_str}</b></span>", unsafe_allow_html=True)
    with colB:
        st.markdown(f"<span class='pill'>Jenis: <b>{jenis}</b></span>", unsafe_allow_html=True)
    with colC:
        # tampilkan label UI agar nampak harga di pilihan
        st.markdown(f"<span class='pill'>Layanan: <b>{layanan_transfer_ui}</b></span>", unsafe_allow_html=True)

    st.write("")  # spacer

    # Dua kolom: kiri (breakdown), kanan (waktu)
    left, right = st.columns([1.6, 1])
    with left:
        st.markdown("<div class='section-title'>➤ Rincian Biaya Tambahan</div>", unsafe_allow_html=True)
        if breakdown_rows:
            df_biaya = pd.DataFrame(breakdown_rows)[["Komponen", "Nominal"]]
            st.table(df_biaya)
        else:
            st.caption("Tidak ada biaya tambahan yang dipilih.")

    with right:
        st.markdown("<div class='section-title'>➤ Waktu</div>", unsafe_allow_html=True)
        st.write(f"• Waktu Transaksi: **{waktu_mulai.strftime('%H:%M')}**")
        st.write(f"• Estimasi Transfer: **{estimasi_selesai_transfer}**")

    # Kartu angka utama (Nominal Transfer, Nominal Transaksi, Biaya Tambahan)
    st.markdown("<div class='card-grid'>", unsafe_allow_html=True)
    st.markdown(f"<div class='card'><h4>Biaya Tambahan Total</h4><p>{format_rupiah(biaya_total)}</p></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='card'><h4>Nominal Transfer</h4><p>{format_rupiah(nominal_transfer)}</p></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='card'><h4>Nominal Transaksi</h4><p>{format_rupiah(nominal_transaksi)}</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.divider()





        





# =============================================
# MENU 2: INPUT DATA TRANSAKSI
# =============================================
elif menu == "Input Data Transaksi":
    st.title("Form Input Data Transaksi")

    # Biaya lain (non-layanan) — tetap tersembunyi dari user
    biaya_opsi = {
        "Biaya administrasi nasabah baru (Rp10.000)": 10_000,
        "Biaya transfer beda bank (Rp10.000)": 10_000,
    }

    # Konfigurasi layanan transfer baru
    SVCS = [
        {"label_ui": "Normal 2 Jam - 2 Jam 30 Menit", "label_ket": "Layanan Transfer Normal", "cost": 0, "normalized": "Normal"},
        {"label_ui": "Kilat Member | Non Member — Rp. 15.000", "label_ket": "Biaya Layanan Transfer Kilat", "cost": 15_000, "normalized": "Kilat"},
        {"label_ui": "Super Kilat Member — Rp. 15.000", "label_ket": "Biaya Layanan Transfer Super Kilat (Member)", "cost": 15_000, "normalized": "Super Kilat"},
        {"label_ui": "Super Kilat Non Member — Rp. 18.000", "label_ket": "Biaya Layanan Transfer Super Kilat (Non Member)", "cost": 18_000, "normalized": "Super Kilat"},
    ]
    SVC_BY_LABEL = {s["label_ui"]: s for s in SVCS}

    with st.form(key="form3"):
        st.subheader("🧾 Data Nasabah & Transaksi")

        # === Input Data Nasabah ===
        col1, col2 = st.columns(2)
        with col1:
            transaksi_no = st.number_input("No. Transaksi", min_value=1, step=1, format="%d")
        with col2:
            nama = st.text_input("Nama Nasabah")

        # === Pilihan Jenis & Kelas ===
        col3, col4 = st.columns(2)
        with col3:
            jenis = st.selectbox("Jenis Nasabah", ["Langganan", "Baru"])
        with col4:
            kelas = st.selectbox("Kelas Nasabah", ["Non Member", "Member Gold", "Member Platinum", "Member Anggota Koperasi"])

        # === Bank & Jenis Gestun ===
        col5, col6 = st.columns(2)
        with col5:
            bank = st.selectbox("Bank Tujuan", ["BCA", "Lainnya"])
        with col6:
            j_g = st.selectbox("Jenis Gestun", ["Kotor", "Bersih"])

        # === Metode & Produk ===
        col7, col8 = st.columns(2)
        with col7:
            metode = st.selectbox("Metode Gestun", ["Konven", "Online"])
        with col8:
            prod = st.text_input("Produk & Sub Produk")

        # === Media & Layanan Transfer ===
        col9, col10 = st.columns(2)
        with col9:
            media = st.selectbox("Media Pencairan", [
                "Mesin EDC - BNI Showroom Gerlong Tonggoh",
                "Mesin EDC - BRI Abadi Cell Sersan",
                "Mesin EDC - BRI Vilan Fashion",
                "Mesin EDC - BCA Idaman Clothes",
                "Mesin EDC - BCA AF Bekasi",
                "Quick Bill - Zahra Fashion",
                "Quick Bill - Phonefoyer",
            ])
        with col10:
            lay = st.selectbox("Jenis Layanan Transfer", [s["label_ui"] for s in SVCS])
            svc = SVC_BY_LABEL[lay]

        # === Rate Jual ===
        rt_type = st.radio("Tipe Rate Jual", ["Persentase (%)", "Nominal (Rp)"], index=0, horizontal=True)
        if rt_type == "Persentase (%)":
            rt_percent = st.number_input("Rate Jual (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.2f", key="rt_percent")
            nominal_rate = 0
            rate_decimal = rt_percent / 100
            rt_str = f"{rt_percent:.2f}%"
        else:
            nominal_rate = st.number_input("Rate Jual (Rp)", min_value=0, step=1000, format="%d", key="rt_nominal")
            rt_percent = 0.0
            rate_decimal = 0
            rt_str = f"Rp {nominal_rate:,}"

        # === Rate MDR ===
        mdr_type = st.radio("Tipe Rate MDR", ["Persentase (%)", "Nominal (Rp)"], index=0, horizontal=True)
        if mdr_type == "Persentase (%)":
            mdr_percent = st.number_input("Rate MDR (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.2f", key="mdr_percent")
            nominal_mdr = 0
            mdr_decimal = mdr_percent / 100
            mdr_str = f"{mdr_percent:.2f}%"
        else:
            nominal_mdr = st.number_input("Rate MDR (Rp)", min_value=0, step=1000, format="%d", key="mdr_nominal")
            mdr_percent = 0.0
            mdr_decimal = 0
            mdr_str = f"Rp {nominal_mdr:,}"

        # === Hitung Rate Untung (Rate Jual - Rate MDR) ===
        if rt_type == "Persentase (%)" and mdr_type == "Persentase (%)":
            ru_percent = rt_percent - mdr_percent
            ru_str = f"{ru_percent:.2f}%"
        elif rt_type == "Nominal (Rp)" and mdr_type == "Nominal (Rp)":
            ru_nominal = nominal_rate - nominal_mdr
            ru_str = f"Rp {ru_nominal:,}"
        else:
            ru_str = f"{rt_str} - {mdr_str}"  # kalau beda tipe

        # === Hitung biaya layanan otomatis ===
        biaya_otomatis = svc["cost"]
        if jenis == "Baru":
            biaya_otomatis += biaya_opsi["Biaya administrasi nasabah baru (Rp10.000)"]
        if bank != "BCA":
            biaya_otomatis += biaya_opsi["Biaya transfer beda bank (Rp10.000)"]
        bl = biaya_otomatis

        # === Input tambahan (Dropdown + Custom Input) ===
        st.markdown("### 🔧 Biaya Tambahan & Hadiah")

        # Biaya EDC
        edc_option = st.selectbox("Biaya Transaksi di Mesin EDC", ["Pilih / Isi Manual", "2.000", "5.000", "10.000"])
        if edc_option == "Pilih / Isi Manual":
            biaya_edc = st.number_input("Isi Biaya EDC (Rp)", min_value=0, step=500)
        else:
            biaya_edc = int(edc_option.replace(".", ""))

        # Biaya QRIS
        qris_option = st.selectbox("Biaya QRIS By WhatsApp", ["Pilih / Isi Manual", "3.000", "5.000", "7.500"])
        if qris_option == "Pilih / Isi Manual":
            biaya_qris = st.number_input("Isi Biaya QRIS (Rp)", min_value=0, step=500)
        else:
            biaya_qris = int(qris_option.replace(".", ""))

        # Hadiah
        hadiah_option = st.selectbox("Hadiah yang Didapatkan", ["Pilih / Isi Manual", "Voucher QRIS", "Voucher Blibli", "Voucher Tokopedia"])
        if hadiah_option == "Pilih / Isi Manual":
            hadiah = st.text_input("Isi Hadiah (misal: Cashback 20k)")
        else:
            hadiah = hadiah_option

        # === Hitung Jumlah Transaksi & Transfer ===
        jt, trf = 0, 0
        if j_g == "Kotor":
            jt = st.number_input("Jumlah Transaksi (Rp)", min_value=0, step=200000, format="%d", key="jt_input")
            if rt_type == "Persentase (%)":
                potongan = int(jt * rate_decimal)
            else:
                potongan = nominal_rate
            trf = jt - potongan - bl
            st.text_input("Jumlah Transfer (Rp)", value=format_rupiah(trf), disabled=True)
        else:
            trf = st.number_input("Jumlah Transfer (Rp)", min_value=0, step=200000, format="%d", key="trf_input")
            if rt_type == "Persentase (%)":
                jt = int((trf / (1 - rate_decimal)) + bl) if rate_decimal < 1 else 0
            else:
                jt = trf + nominal_rate + bl
            st.text_input("Jumlah Transaksi (Rp)", value=format_rupiah(jt), disabled=True)

        st.number_input("Biaya Layanan (Rp)", value=bl, format="%d", disabled=True)

        # Keterangan otomatis
        lines = []
        if jenis == "Baru":
            lines.append("Biaya Layanan Administrasi Nasabah Baru")
        if bank != "BCA":
            lines.append("Biaya Layanan Transfer diluar Bank BCA")
        if svc["cost"] > 0:
            lines.append(svc["label_ket"])
        default_ket = " & ".join(lines) if lines else "-"
        ket = st.text_area("Keterangan Layanan", value=default_ket, height=80)

        submit = st.form_submit_button("Generate WhatsApp Text")

    # OUTPUT setelah submit
    if submit:
        jt_fmt = format_rupiah(jt)
        trf_fmt = format_rupiah(trf)
        bl_fmt = format_rupiah(bl)
        edc_fmt = format_rupiah(biaya_edc)
        qris_fmt = format_rupiah(biaya_qris)

        def fmt_heading(txt): return f"*{txt}*"
        def fmt_value(txt): return f"_{txt}_" if jenis == "Langganan" else f"*{txt}*"
        bullet = "•"
        sep = "_______________________________"

        teks_output = f"""
{bullet} {fmt_heading(f"TRANSAKSI NO. {transaksi_no}")}  
{sep}  
{bullet} {fmt_heading('DATA NASABAH')}  
   {bullet} Nama Nasabah : {fmt_value(nama)}  
   {bullet} Jenis Nasabah : {fmt_value(jenis)} | {fmt_value(kelas)}  
{sep}  
   {bullet} Jenis Media Pencairan : {fmt_value(media)}  
   {bullet} Produk : {fmt_value(prod)}  
   {bullet} Rate Jual : {fmt_value(rt_str)}  
   {bullet} Rate Untung : {fmt_value(ru_str)}  
   {bullet} Layanan Transfer : {fmt_value(lay)}  
   {bullet} Nominal Transaksi : {fmt_value(jt_fmt)}  
   {bullet} Biaya Layanan Transfer: {fmt_value(bl_fmt)}  
   {bullet} Biaya Transaksi di Mesin EDC : {fmt_value(edc_fmt)}  
   {bullet} Biaya QRIS By Whatsapp : {fmt_value(qris_fmt)}  
   {bullet} Hadiah yang didapatkan : {fmt_value(hadiah)}  
{sep}  
{bullet} {fmt_heading(f"Jumlah Transfer {trf_fmt}")}  
"""
        st.code(teks_output, language="text")





# =============================================
# MENU 3: Pembagian Transaksi EDC
# =============================================

elif menu == "Proporsional Transaksi Besar":
    menu_pembagian_edc()

# =============================================
# MENU 4: Jam
# =============================================
elif menu == "Jam":
    st.title("⏱️ Hitung Selisih Waktu Antar Jam")

    # Atur default sekali saja
    if "start_time" not in st.session_state:
        st.session_state.start_time = datetime.now(ZoneInfo("Asia/Jakarta")).time()
    if "end_time" not in st.session_state:
        st.session_state.end_time = datetime.now(ZoneInfo("Asia/Jakarta")).time()

    # Panggil widget hanya dengan key, tanpa value
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