from __future__ import annotations

import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+
import streamlit.components.v1 as components
import random
from typing import List, Tuple, Dict
import pandas as pd

# --- Fungsi Pendukung ---
def estimasi_durasi(layanan):
    if layanan == "Super Kilat":
        return timedelta(minutes=20)
    elif layanan == "Kilat":
        return timedelta(minutes=40)
    else:
        return timedelta(hours=2, minutes=30)

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
    """Split *total* across *machines*, keeping NOMINAL < limit‑SAFETY_GAP,
    non‑round, max *max_swipes* per machine, and guaranteeing exact total.
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

    # Exact‑total adjustment
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
        "Masukkan Total Transaksi (Rp)", min_value=100_000_000, step=10_000_000, format="%d"
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

# If you want to test this file standalone, uncomment below:
# if __name__ == "__main__":
#     import streamlit.runtime.scriptrunner.script_run_context as stc
#     if stc.get_script_run_ctx():
#         menu_pembagian_edc()

# --- App Config ---
st.set_page_config(page_title="Input Data Transaksi Gestun", layout="centered")

menu = st.sidebar.selectbox("Pilih Menu", [
    "Hitung Nominal Transaksi",
    "Input Data Transaksi",
    "Proporsional Transaksi Besar",
])

# ===============================
# MENU 1: HITUNG NOMINAL TRANSAKSI
# ===============================
if menu == "Hitung Nominal Transaksi":
    st.header("💰 Hitung Nominal Transaksi")

    # Pilihan jenis & rate
    jenis = st.selectbox("Pilih Jenis Perhitungan:", ["Gesek Kotor", "Gesek Bersih"])
    rate_dict = {
        "2.5% Visa & Master Card": 0.975,
        "2.6% Visa & Master Card": 0.974,
        "3.5% BCA Card": 0.965,
        "4.7% AMEX": 0.953,
    }
    rate_label = st.selectbox("Pilih Rate Jual:", list(rate_dict.keys()))

    # Pilihan Biaya Tambahan & Layanan Transfer
    biaya_opsi = {
        "Biaya administrasi nasabah baru (Rp10.000)": 10000,
        "Biaya layanan super kilat (Rp18.000)": 18000,
        "Biaya layanan kilat (Rp15.000)": 15000,
        "Biaya transfer beda bank (Rp10.000)": 10000,
        "Tidak ada tambahan biaya layanan": 0
    }

    layanan_transfer = st.selectbox("Pilih Layanan Transfer:", ["Normal", "Kilat", "Super Kilat"])
    biaya_tambahan_opsi = [
        k for k in biaya_opsi
        if "layanan kilat" not in k.lower()
        and "super kilat" not in k.lower()
        and "tidak ada" not in k.lower()
    ]

    biaya_pilihan = st.multiselect("Pilih Biaya Tambahan Lainnya:", biaya_tambahan_opsi)
    biaya_total = sum(biaya_opsi[b] for b in biaya_pilihan)
    if layanan_transfer == "Kilat":
        biaya_total += biaya_opsi["Biaya layanan kilat (Rp15.000)"]
    elif layanan_transfer == "Super Kilat":
        biaya_total += biaya_opsi["Biaya layanan super kilat (Rp18.000)"]

    st.write(f"▶️ Total Biaya Tambahan: {format_rupiah(biaya_total)}")
    rate = rate_dict.get(rate_label, 1)

    # --- Callback untuk memformat input secara real-time ---
    def format_rupiah_input(key):
        txt = st.session_state.get(key, "")
        digits = "".join([c for c in txt if c.isdigit()])
        st.session_state[key] = "{:,}".format(int(digits)).replace(",", ".") if digits else ""

    # Inisialisasi session_state (hanya sekali)
    if "nominal_input" not in st.session_state:
        st.session_state.nominal_input = ""

    # Text input yang memanggil callback format_nominal
    st.text_input(
    label=f"Masukkan nominal {'Transaksi (Gesek Kotor)' if jenis == 'Gesek Kotor' else 'Transfer Diterima (Gesek Bersih)'} (Rp):",
    key="nominal_input",
    on_change=format_rupiah_input,
    args=("nominal_input",),
    )

    # <<–– Blok konversi harus tetap ada ––>>
    raw = st.session_state.nominal_input.replace(".", "")
    if raw.isdigit():
        nominal_int = int(raw)
    else:
        nominal_int = 0

    # --- Tombol Hitung Sekarang (harus di dalam blok ini) ---
    if st.button("Hitung Sekarang", disabled=(nominal_int <= 0)):
        waktu_mulai = datetime.now(ZoneInfo("Asia/Jakarta"))
        estimasi_selesai_transfer = estimasi_selesai(
            waktu_mulai, estimasi_durasi(layanan_transfer)
        )

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown(
                "<h2 style='text-align: center;'>📊 Hasil Perhitungan</h2>",
                unsafe_allow_html=True
            )
            st.markdown(
                f"<p style='font-size:1.35rem;'><strong>➤ Jenis Perhitungan:</strong> {jenis}</p>",
                unsafe_allow_html=True
            )
            st.markdown(
                f"<p style='font-size:1.35rem;'><strong>➤ Rate Jual:</strong> {tampilkan_rate(rate)}</p>",
                unsafe_allow_html=True
            )
            st.markdown(
                f"<p style='font-size:1.35rem;'><strong>➤ Biaya Tambahan Total:</strong> {format_rupiah(biaya_total)}</p>",
                unsafe_allow_html=True
            )

            if nominal_int > 0:
                if jenis == "Gesek Kotor":
                    nominal_transfer = int(nominal_int * rate - biaya_total)
                    st.markdown(
                        f"<p style='font-size:1.35rem;'><strong>➤ Nominal Transfer:</strong> {format_rupiah(nominal_transfer)}</p>",
                        unsafe_allow_html=True
                    )
                    st.markdown(
                        f"<p style='font-size:1.35rem;'><strong>➤ Nominal Transaksi:</strong> {format_rupiah(nominal_int)}</p>",
                        unsafe_allow_html=True
                    )
                else:  # Gesek Bersih
                    fee = int(nominal_int / rate - nominal_int)
                    nominal_transaksi = nominal_int + fee + biaya_total
                    st.markdown(
                        f"<p style='font-size:1.35rem;'><strong>➤ Nominal Transfer:</strong> {format_rupiah(nominal_int)}</p>",
                        unsafe_allow_html=True
                    )
                    st.markdown(
                        f"<p style='font-size:1.35rem;'><strong>➤ Nominal Transaksi:</strong> {format_rupiah(nominal_transaksi)}</p>",
                        unsafe_allow_html=True
                    )

                st.markdown(
                    f"<p style='font-size:1.35rem;'><strong>➤ Waktu Transaksi:</strong> {waktu_mulai.strftime('%H:%M')}</p>",
                    unsafe_allow_html=True
                )
                st.markdown(
                    f"<p style='font-size:1.35rem;'><strong>➤ Waktu Estimasi Transfer:</strong> {estimasi_selesai_transfer}</p>",
                    unsafe_allow_html=True
                )
            else:
                st.error("Masukkan nominal transaksi/transf sebesar lebih dari 0 terlebih dahulu.")

# =============================================
# MENU 2: INPUT DATA TRANSAKSI GESTUN
# =============================================
elif menu == "Input Data Transaksi Gestun":
    st.title("Form Input Data Transaksi Gestun")

    # Semua opsi biaya tambahan (tidak ditampilkan ke user)
    biaya_opsi = {
        "Biaya administrasi nasabah baru (Rp10.000)": 10000,
        "Biaya layanan super kilat (Rp18.000)": 18000,
        "Biaya layanan kilat (Rp15.000)": 15000,
        "Biaya transfer beda bank (Rp10.000)": 10000,
    }

    with st.form(key="form3"):
        st.subheader("🧾 Data Nasabah & Transaksi")

        # === BARIS 1 ===
        col1, col2 = st.columns(2)
        with col1:
            transaksi_no = st.number_input("No. Transaksi", min_value=1, step=1, format="%d")
        with col2:
            nama = st.text_input("Nama Nasabah")

        # === BARIS 2 ===
        col3, col4 = st.columns(2)
        with col3:
            jenis = st.selectbox("Jenis Nasabah", ["Langganan", "Baru"])
        with col4:
            kelas = st.selectbox("Kelas Nasabah", [
                "Non Member", "Member Gold", "Member Platinum", "Member Anggota Koperasi"
            ])

        # === BARIS 3 ===
        col5, col6 = st.columns(2)
        with col5:
            bank = st.selectbox("Bank Tujuan", ["BCA", "Lainnya"])
        with col6:
            j_g = st.selectbox("Jenis Gestun", ["Kotor", "Bersih"])

        # === BARIS 4 ===
        col7, col8 = st.columns(2)
        with col7:
            metode = st.selectbox("Metode Gestun", ["Konven", "Online"])
        with col8:
            prod = st.text_input("Produk & Sub Produk")

        # === BARIS 5 ===
        col9, col10 = st.columns(2)
        with col9:
            rt_percent = st.number_input("Rate Jual (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.2f")
        with col10:
            lay = st.selectbox("Jenis Layanan Transfer", ["Normal", "Kilat", "Super Kilat"])

        rt_str = f"{rt_percent:.2f}%"
        rate_decimal = rt_percent / 100 if rt_percent else 0

        # Hitung biaya layanan otomatis
        biaya_otomatis = 0
        if lay == "Kilat":
            biaya_otomatis += biaya_opsi["Biaya layanan kilat (Rp15.000)"]
        elif lay == "Super Kilat":
            biaya_otomatis += biaya_opsi["Biaya layanan super kilat (Rp18.000)"]
        if jenis == "Baru":
            biaya_otomatis += biaya_opsi["Biaya administrasi nasabah baru (Rp10.000)"]
        if bank != "BCA":
            biaya_otomatis += biaya_opsi["Biaya transfer beda bank (Rp10.000)"]

        bl = biaya_otomatis

        # HITUNG JUMLAH TRANSAKSI & TRANSFER
        jt, trf = 0, 0

        if j_g == "Kotor":
            # Gunakan input angka untuk Jumlah Transaksi
            jt = st.number_input("Jumlah Transaksi (Rp)", min_value=0, step=200000, format="%d", key="jt_input")
            trf = jt - int(jt * rate_decimal) - bl
            trf_str = format_rupiah(trf)
            st.text_input("Jumlah Transfer (Rp)", value=trf_str, disabled=True)

        else:
            # Gunakan input angka untuk Jumlah Transfer
            trf = st.number_input("Jumlah Transfer (Rp)", min_value=0, step=200000, format="%d", key="trf_input")
            jt = int((trf / (1 - rate_decimal)) + bl) if rate_decimal < 1 else 0
            jt_str = format_rupiah(jt)
            st.text_input("Jumlah Transaksi (Rp)", value=jt_str, disabled=True)


        # BIAYA LAYANAN
        st.number_input(
            "Biaya Layanan (Rp)",
            value=bl,
            format="%d",
            disabled=True,
            help="Biaya layanan dihitung otomatis"
        )

        # KETERANGAN OTOMATIS
        lines = []
        if jenis == "Baru":
            lines.append("Biaya Layanan Administrasi Nasabah Baru")
        if bank != "BCA":
            lines.append("Biaya Layanan Transfer diluar Bank BCA")
        if lay == "Kilat":
            lines.append("Biaya Layanan Transfer Kilat")
        elif lay == "Super Kilat":
            lines.append("Biaya Layanan Transfer Super Kilat")
        default_ket = " & ".join(lines) if lines else ""

        ket = st.text_area("Keterangan Layanan", value=default_ket, height=80)

        submit = st.form_submit_button("Generate WhatsApp Text")

    if submit:
        jt_fmt = format_rupiah(jt)
        trf_fmt = format_rupiah(trf)
        bl_fmt = format_rupiah(bl)

        def fmt_heading(txt): return f"*{txt}*"
        def fmt_value(txt): return f"_{txt}_" if jenis == "Langganan" else f"*{txt}*"
        bullet = "•"
        sep = "_______________________________"

        teks_output = f"""
{bullet} {fmt_heading(f"TRANSAKSI NO. {transaksi_no}")}
{sep}
{bullet} {fmt_heading('DATA NASABAH')}
   {bullet} Nama Nasabah : {fmt_value(nama)}
   {bullet} Jenis Nasabah : {fmt_value(jenis)}
   {bullet} Kelas Nasabah : {fmt_value(kelas)}
{sep}
{bullet} {fmt_heading('DATA TRANSAKSI')}
   {bullet} Jenis Gestun : {fmt_value(j_g)}
   {bullet} Metode Gestun : {fmt_value(metode)}
   {bullet} Jenis Layanan Transfer: {fmt_value(lay)}
   {bullet} Produk & Sub Produk : {fmt_value(prod)}
   {bullet} Rate Jual : {fmt_value(rt_str)}
{sep}
{bullet} {fmt_heading('RANGKUMAN BIAYA DAN TRANSAKSI')}
   {bullet} Jumlah Transaksi : {fmt_value(jt_fmt)}
   {bullet} Biaya Layanan : {fmt_value(bl_fmt)}
   {bullet} Keterangan Layanan : {fmt_value(ket)}
{sep}
{bullet} {fmt_heading(f"Jumlah Transfer {trf_fmt}")}
"""
        st.code(teks_output, language="text")

# =============================================
# MENU 3: Pembagian Transaksi EDC
# =============================================

elif menu == "Proporsional Transaksi Besar":
    menu_pembagian_edc()