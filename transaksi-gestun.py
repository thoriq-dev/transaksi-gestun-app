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
    st.header("💰 Konvensional")
    col_input, col_output = st.columns([1.3, 1])
    with col_input:
        jenis = st.selectbox("Pilih Jenis Perhitungan:", ["Gesek Kotor", "Gesek Bersih"])

        tipe_rate = st.selectbox(
            "Tipe Rate Jual:",
            ["Persentase (%)", "Nominal (Rp)"],
            key="menu1_tipe_rate"
        )
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
            if rt_percent >= 100.0:
                st.error("Rate tidak boleh 100% atau lebih.")
                st.stop()
            rate_decimal = rt_percent / 100.0
            nominal_rate = 0
            rt_str = f"{rt_percent:.2f}%"
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
        BIAYA_TAMBAHAN = {
            "Biaya administrasi nasabah baru": 10_000,
            "Biaya transfer beda bank": 10_000,
            "Biaya transaksi di mesin edc": 2_000,
            "Biaya qris by whatsapp": 3_000,
        }
        SVCS = [
            {"label_ui": "Normal", "label_biaya": "Layanan normal", "cost": 0, "normalized": "Normal"},
            {"label_ui": f"Kilat Member | Non Member — {fmt_rp(15_000)}", "label_biaya": "Biaya layanan kilat", "cost": 15_000, "normalized": "Kilat"},
            {"label_ui": f"Super Kilat Member — {fmt_rp(15_000)}", "label_biaya": "Biaya layanan super kilat (member)", "cost": 15_000, "normalized": "Super Kilat"},
            {"label_ui": f"Super Kilat Non Member — {fmt_rp(18_000)}", "label_biaya": "Biaya layanan super kilat (non member)", "cost": 18_000, "normalized": "Super Kilat"},
        ]
        SVC_BY_LABEL = {s["label_ui"]: s for s in SVCS}
        layanan_transfer_ui = st.selectbox(
            "Pilih Layanan Transfer:",
            [s["label_ui"] for s in SVCS],
            key="menu1_layanan_transfer"
        )
        svc = SVC_BY_LABEL[layanan_transfer_ui]
        biaya_pilihan = st.multiselect(
            "Pilih Biaya Tambahan Lainnya:",
            list(BIAYA_TAMBAHAN.keys()),
            key="menu1_biaya_pilihan"
        )
        biaya_total = sum(BIAYA_TAMBAHAN[b] for b in biaya_pilihan) + svc["cost"]
        st.write(f"▶️ Total Biaya Tambahan: {format_rupiah(biaya_total)}")
        breakdown_rows = [
            {"Komponen": b, "Nominal": format_rupiah(BIAYA_TAMBAHAN[b])}
            for b in biaya_pilihan
        ]
        if svc["cost"] > 0:
            breakdown_rows.append({"Komponen": svc["label_biaya"], "Nominal": format_rupiah(svc["cost"])})
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
        st.markdown("<style>.stButton>button{width:100%;}</style>", unsafe_allow_html=True)
        hitung_clicked = st.button("Hitung Sekarang", disabled=(nominal_int <= 0))
    with col_output:
        st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)
        if not hitung_clicked:
            st.info("Isi form di kiri dan tekan **Hitung Sekarang** untuk melihat hasil di sini.")
        else:
            st.markdown("""
                <style>
                .card-grid {display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 10px;}
                .card {border: 1px solid #e8e8e8; border-radius: 14px; padding: 14px 16px;}
                .card h4 {margin: 0 0 8px 0; font-size: 1rem; color: #6b7280;}
                .card p {margin: 0; font-weight: 700; font-size: 1.25rem;}
                .pill {
                    display:inline-block; 
                    padding:4px 12px; 
                    border-radius:9999px; 
                    background:#f0f9ff; 
                    color:#0369a1;
                    border:1px solid #bae6fd;
                    font-size:0.9rem;
                    font-weight:600;
                }
                .section-title {
                    font-size:1.1rem; 
                    font-weight:700; 
                    margin: 14px 0 8px 0; 
                    color:#0f172a;
                }
                </style>
            """, unsafe_allow_html=True)
            waktu_mulai = datetime.now(ZoneInfo("Asia/Jakarta"))
            durasi = estimasi_durasi(svc["normalized"])
            estimasi_selesai_transfer = estimasi_selesai(waktu_mulai, durasi)

            EXTRA_FEE_BERSIH = 1_000

            if jenis == "Gesek Kotor":
                if tipe_rate == "Persentase (%)":
                    fee_rupiah = int(round(nominal_int * rate_decimal))
                    nominal_transfer = int(round(nominal_int * (1 - rate_decimal))) - biaya_total
                else:
                    fee_rupiah = nominal_rate
                    nominal_transfer = nominal_int - nominal_rate - biaya_total

                nominal_transfer = max(0, nominal_transfer)
                nominal_transaksi = nominal_int
            else:
                # Gesek Bersih (MODEL gross-up net + biaya_total + 1.000)
                if tipe_rate == "Persentase (%)":
                    nominal_transaksi = int((nominal_int + biaya_total) / (1 - rate_decimal)) + EXTRA_FEE_BERSIH
                    fee_rupiah = int(nominal_transaksi * rate_decimal)
                else:
                    nominal_transaksi = nominal_int + biaya_total + nominal_rate + EXTRA_FEE_BERSIH
                    fee_rupiah = nominal_rate + EXTRA_FEE_BERSIH

                nominal_transfer = nominal_int
            if tipe_rate == "Persentase (%)":
                if jenis == "Gesek Kotor":
                    fee_info = (
                        f"💡 Fee {rt_str} dari {format_rupiah(nominal_int)} "
                        f"adalah {format_rupiah(fee_rupiah)}"
                    )
                else:
                    fee_info = (
                        f"💡 Fee {rt_str} dari {format_rupiah(nominal_int)} (bersih, gross-up biaya) "
                        f"adalah {format_rupiah(fee_rupiah)}"
                    )
            else:
                if jenis == "Gesek Bersih":
                    fee_info = (
                        f"💡 Fee tetap sebesar {format_rupiah(fee_rupiah)} "
                        f"(rate nominal + tambahan bersih {format_rupiah(EXTRA_FEE_BERSIH)})."
                    )
                else:
                    fee_info = (
                        f"💡 Fee tetap sebesar {format_rupiah(fee_rupiah)} "
                        f"berdasarkan nilai rate nominal."
                    )

            st.caption(fee_info)
            colA, colB, colC = st.columns(3)
            with colA:
                st.markdown(f"<span class='pill'>Rate: <b>{rt_str}</b></span>", unsafe_allow_html=True)
            with colB:
                st.markdown(f"<span class='pill'>Jenis: <b>{jenis}</b></span>", unsafe_allow_html=True)
            with colC:
                st.markdown(f"<span class='pill'>Layanan: <b>{layanan_transfer_ui}</b></span>", unsafe_allow_html=True)
            st.markdown("<div class='section-title'>➤ Rincian Biaya Tambahan</div>", unsafe_allow_html=True)
            if breakdown_rows:
                df_biaya = pd.DataFrame(breakdown_rows)[["Komponen", "Nominal"]]
                st.table(df_biaya)
            else:
                st.caption("Tidak ada biaya tambahan yang dipilih.")
            st.markdown("<div class='section-title'>➤ Waktu</div>", unsafe_allow_html=True)
            if waktu_mulai and estimasi_selesai_transfer:
                st.write(f"• Waktu Transaksi: **{waktu_mulai.strftime('%H:%M')}**")
                st.write(f"• Estimasi Transfer: **{estimasi_selesai_transfer}**")
            else:
                st.caption("Tekan tombol 'Hitung Sekarang' untuk menampilkan estimasi waktu.")
            st.markdown("<div class='card-grid'>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='card'><h4>Biaya Tambahan Total</h4><p>{format_rupiah(biaya_total)}</p></div>",
                unsafe_allow_html=True
            )
            st.markdown(
                f"<div class='card'><h4>Nominal Transfer</h4><p>{format_rupiah(nominal_transfer)}</p></div>",
                unsafe_allow_html=True
            )
            st.markdown(
                f"<div class='card'><h4>Nominal Transaksi</h4><p>{format_rupiah(nominal_transaksi)}</p></div>",
                unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)
            st.divider()


# =============================================
# MENU 2: INPUT DATA TRANSAKSI
# =============================================
elif menu == "Input Data":
    st.title("Form Input Data Transaksi")

    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    def format_rupiah(angka):
        return f"Rp {angka:,.0f}".replace(",", ".")

    SVCS = [
        {"label_ui": "Normal 3 Jam", "cost": 0, "normalized": "Normal"},
        {"label_ui": "Express Member — Rp. 15.000", "cost": 15000, "normalized": "Express"},
        {"label_ui": "Express Non Member — Rp. 18.000", "cost": 18000, "normalized": "Express"},
    ]
    SVC_BY_LABEL = {s["label_ui"]: s for s in SVCS}

    st.subheader("🧾 Data Transaksi")
    transaksi_no = st.number_input("No. Transaksi", min_value=1, step=1, format="%d")

    metode_transaksi = st.selectbox("Metode Transaksi", ["Konven", "Online"], key="metode_transaksi_inputdata")

    lay = st.selectbox("Jenis Layanan Transfer", [s["label_ui"] for s in SVCS])
    svc = SVC_BY_LABEL[lay]

    if "Express" in lay:
        with st.form(key="form_super"):
            st.markdown("### ⚡ Mode: Express")

            nama = st.text_input("Nama Nasabah")
            kategori = st.selectbox("Kategori Nasabah", ["Langganan", "Baru"])
            kelas = st.selectbox(
                "Kelas Nasabah",
                ["Non Member", "Gold", "Platinum", "Prioritas", "Silver"]
            )

            metode = st.selectbox("Metode Perhitungan", ["Gesek Kotor", "Gesek Bersih"])

            fee_type = st.selectbox("Jenis Fee", ["Persentase (%)", "Flat (Rp)"])
            if fee_type == "Persentase (%)":
                fee_persen = st.number_input("Fee (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.2f")
                fee_decimal = fee_persen / 100
                fee_flat = 0
            else:
                fee_flat = st.number_input("Fee Flat (Rp)", min_value=0, step=1000, format="%d")
                fee_decimal = 0
                fee_persen = 0

            st.markdown("### 💰 Biaya Layanan Tambahan")

            EXTRA_BIAYA = [
                {"key": "transfer_non_bca", "label": "Biaya Transfer Selain Bank BCA", "default": 10_000, "step": 10_000},
                {"key": "edc",              "label": "Biaya Transaksi di Mesin EDC",     "default": 2_000,  "step": 2_000},
                {"key": "qris_wa",          "label": "Biaya Layanan QRIS By WhatsApp",   "default": 3_000,  "step": 3_000},
                {"key": "manual",           "label": "Lainnya / Custom",                 "default": 0,      "step": 1_000},
            ]

            extra_labels = [x["label"] for x in EXTRA_BIAYA]
            biaya_pilihan = st.multiselect(
                "Pilih biaya yang dipakai",
                options=extra_labels,
                default=[],
                key="super_biaya_pilihan_satset"
            )

            biaya_layanan_input = 0
            biaya_detail = []

            for opt in EXTRA_BIAYA:
                if opt["label"] not in biaya_pilihan:
                    continue

                val = int(opt["default"])

                if opt["key"] == "manual":
                    val = st.number_input(
                        f"{opt['label']} (Rp)",
                        min_value=0,
                        step=opt["step"],
                        value=opt["default"],
                        format="%d",
                        key=f"super_biaya_{opt['key']}_val"
                    )
                    val = int(val)
                else:
                    edit = st.checkbox(
                        f"Edit {opt['label']}?",
                        value=False,
                        key=f"super_biaya_{opt['key']}_edit"
                    )
                    if edit:
                        val = st.number_input(
                            f"Nominal {opt['label']} (Rp)",
                            min_value=0,
                            step=opt["step"],
                            value=opt["default"],
                            format="%d",
                            key=f"super_biaya_{opt['key']}_val"
                        )
                        val = int(val)

                biaya_layanan_input += val
                biaya_detail.append((opt["label"], val))

            biaya_super_kilat = svc["cost"]

            biaya_baru = 10_000 if kategori == "Baru" else 0

            biaya_layanan_total = biaya_layanan_input + biaya_super_kilat + biaya_baru

            st.markdown("---")

            if metode == "Gesek Kotor":
                jt_input = st.number_input("Jumlah Transaksi (Rp)", min_value=0, step=200000, format="%d")

                if fee_type == "Persentase (%)":
                    fee = int(jt_input * fee_decimal)
                else:
                    fee = int(fee_flat)

                jumlah_transfer = jt_input - fee - biaya_layanan_total
                jumlah_transaksi = jt_input

            else:
                trf_input = st.number_input("Jumlah Transfer (Rp)", min_value=0, step=200000, format="%d")

                if fee_type == "Persentase (%)":
                    jumlah_transaksi = int((trf_input + biaya_layanan_total) / (1 - fee_decimal)) + 1000
                    fee = int(jumlah_transaksi * fee_decimal)
                else:
                    jumlah_transaksi = trf_input + biaya_layanan_total + fee_flat
                    fee = fee_flat

                jumlah_transfer = trf_input

            jt_fmt = format_rupiah(jumlah_transaksi)
            trf_fmt = format_rupiah(jumlah_transfer)
            fee_fmt = format_rupiah(fee)
            biaya_fmt = format_rupiah(biaya_layanan_total)

            estimasi = timedelta(minutes=20)
            waktu_selesai = (datetime.now(ZoneInfo("Asia/Jakarta")) + estimasi).strftime("%H:%M WIB")

            st.text_input("Jumlah Transaksi (Rp)", value=jt_fmt, disabled=True)
            st.text_input("Fee (Rp)", value=fee_fmt, disabled=True)
            st.text_input("Total Biaya Layanan (Rp)", value=biaya_fmt, disabled=True)
            st.text_input("Jumlah Transfer (Rp)", value=trf_fmt, disabled=True)

            submit = st.form_submit_button("Generate WhatsApp Text")

            if submit:
                rate_jual = fee_persen

                if biaya_detail:
                    biaya_lines = "\n".join([f"• {lbl} : {format_rupiah(val)}" for lbl, val in biaya_detail])
                else:
                    biaya_lines = "• (Tidak ada biaya tambahan)"

                teks_output = f"""
TRANSAKSI NO. {transaksi_no} ({metode_transaksi.upper()})
EXPRESS

• Nama Nasabah : {nama}
• Kategori Nasabah : {kategori}
• Kelas Nasabah : {kelas}
• Rate Jual : {rate_jual:.2f}%
• Jumlah Transfer : *{trf_fmt}*
_______________________________
Estimasi Selesai: {waktu_selesai}
"""
                st.code(teks_output, language="text")
    else:
        st.markdown("### 🕓 Mode: Normal 3 Jam")

        tab1, tab2, tab3 = st.tabs(["🧍 Data Nasabah", "💳 Detail Transaksi", "💰 Biaya & Hasil"])

        with tab1:
            st.subheader("🧍 Data Nasabah")
            nama = st.text_input("Nama Nasabah")
            jenis = st.selectbox("Kategori Nasabah", ["Langganan", "Baru"])
            kelas = st.selectbox("Kelas Nasabah", ["Non Member", "Gold", "Platinum", "Prioritas", "Silver"])

        with tab2:
            st.subheader("💳 Detail Transaksi")
            LIST_MEDIA = [
                "Mesin EDC - BNI Blurry Fashion Store",
                "Mesin EDC - BRI Abadi Cell Sersan",
                "Mesin EDC - BCA Abadi Fashion Malang",
                "Mesin EDC - BCA Idaman Clothes",
                "Mesin EDC - BCA AF Bekasi",
                "QRIS Statis - BNI Indah Mebeul",
                "QRIS Statis - BNI Bahagia Roastery",
                "QRIS Statis - BNI Toko Jaya Grosir",
                "QRIS Statis - BNI Bajuri Bike Center",
                "QRIS Statis - BNI Sinar Elektronik Store",
                "QRIS Statis - BRI Vilan Fashion",
                "QRIS Statis - BRI Abadi Cell",
                "Paper Id X Blibli - Kreasi Mode",
                "Paper Id X Blibli - Happy Fashion",
                "Paper Id - Kreasi Mode",
                "Paper Id - Happy Fashion",
                "Quickbill WL - Phonefoyer",
                "Quickbill  - Phonefoyer",
                "Lainnya / Custom"
            ]
            pilihan_media = st.selectbox("Jenis Media Pencairan", LIST_MEDIA)
            if pilihan_media == "Lainnya / Custom":
                media_custom = st.text_input("Tulis Nama Media Pencairan", placeholder="Contoh: EDC Mandiri - Toko Baru")
                media = media_custom 
            else:
                media = pilihan_media
            CC_BANKS = [
                "CC - BCA", "CC - Mandiri", "CC - BNI", "CC - BRI", "CC - BSI", "CC - BTN",
                "CC - CIMB Niaga", "CC - Danamon", "CC - PermataBank", "CC - Mega",
                "CC - Maybank", "CC - OCBC NISP", "CC - UOB", "CC - HSBC",
                "CC - DBS", "CC - Standard Chartered", "CC - PaninBank",
                "CC - Sinarmas", "CC - Honest", "CC - Atome",
            ]
            PAYLATER = [
                "PayLater - Shopee PayLater",
                "PayLater - GoPayLater",
                "PayLater - OVO PayLater",
                "PayLater - DANA PayLater",
                "PayLater - Kredivo",
                "PayLater - Akulaku",
                "PayLater - Atome",
                "PayLater - Indodana",
                "PayLater - Blibli/Tiket PayLater",
                "PayLater - Traveloka PayLater",
                "PayLater - BCA PayLater",
                "PayLater - BRI Ceria",
                "PayLater - Credinex",
                "PayLater - Akulaku PayLater",
                "PayLater - HomeCredit Bayar Nanti",
                "PayLater - Lazada PayLater",
                "PayLater - Sampurna YUP",
            ]

            PRODUCT_GROUPS = {
                "Kartu Kredit": CC_BANKS,
                "PayLater": PAYLATER,
            }

            st.markdown("### Produk")
            kategori_produk = st.selectbox(
                "Kategori Produk",
                ["Kartu Kredit", "PayLater", "Lainnya / Tulis Bebas"],
                index=0
            )

            if kategori_produk in PRODUCT_GROUPS:
                options = PRODUCT_GROUPS[kategori_produk] + ["Lainnya / Custom..."]
                produk_pilihan = st.selectbox(f"Pilih {kategori_produk}", options, index=0)
                if produk_pilihan == "Lainnya / Custom...":
                    contoh = "CC - BCA Visa Platinum" if kategori_produk == "Kartu Kredit" else "PayLater - <Nama Provider>"
                    produk = st.text_input("Tulis Produk", placeholder=f"Contoh: {contoh}")
                else:
                    produk = produk_pilihan
            else:
                produk = st.text_input("Tulis Produk", placeholder="Contoh: CC - BCA / PayLater - Kredivo")

            produk = (produk or "").strip()

            rt_type = st.radio("Tipe Rate Jual", ["Persentase (%)", "Nominal (Rp)"], key="rt_type", horizontal=True)
            if rt_type == "Persentase (%)":
                rt_percent = st.number_input("Rate Jual (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.2f")
                rate_decimal = rt_percent / 100
                nominal_rate = 0
                rt_str = f"{rt_percent:.2f}%"
            else:
                nominal_rate = st.number_input("Rate Jual (Rp)", min_value=0, step=1000, format="%d")
                rate_decimal = 0
                rt_percent = 0
                rt_str = f"Rp {nominal_rate:,}"

            mdr_percent = st.number_input("Rate MDR (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.2f")

            j_g = st.selectbox("Jenis Gestun", ["Kotor", "Bersih"])
            if j_g == "Kotor":
                jt = st.number_input("Jumlah Transaksi (Rp)", min_value=0, step=200000, format="%d")
                potongan = int(jt * rate_decimal) if rt_type == "Persentase (%)" else nominal_rate
                trf = jt - potongan
            else:
                trf = st.number_input("Jumlah Transfer (Rp)", min_value=0, step=200000, format="%d")
                jt = (
                    int(round(trf / (1 - rate_decimal)))
                    if rate_decimal and 0 < rate_decimal < 1
                    else int(trf + (nominal_rate or 0))
                ) + 1000

            if rt_type == "Persentase (%)":
                ru_str = f"{rt_percent - mdr_percent:.2f}%"
            else:
                mdr_rp = jt * (mdr_percent / 100) if j_g == "Kotor" else trf * (mdr_percent / 100)
                rate_untung_rp = nominal_rate - mdr_rp
                ru_str = f"Rp {rate_untung_rp:,.0f}".replace(",", ".")

        with tab3:
            st.subheader("💰 Biaya & Hasil")

            col1, col2, col3 = st.columns(3)
            with col1:
                biaya_transfer = st.number_input(
                    "Biaya Transfer Selain Bank BCA (Rp)",
                    min_value=0,
                    step=10_000,
                    value=0,
                    format="%d"
                )
            with col2:
                biaya_edc = st.number_input(
                    "Biaya Transaksi di Mesin EDC (Rp)",
                    min_value=0,
                    step=2_000,
                    value=0,
                    format="%d"
                )
            with col3:
                biaya_qris_wa = st.number_input(
                    "Biaya Layanan QRIS By WhatsApp (Rp)",
                    min_value=0,
                    step=3_000,
                    value=0,
                    format="%d"
                )

            biaya_super = 0
            biaya_baru = 10_000 if jenis == "Baru" else 0

            total_biaya = (
                biaya_super
                + biaya_baru
                + biaya_transfer
                + biaya_edc
                + biaya_qris_wa
            )

            jt_final = jt + total_biaya if j_g == "Bersih" else jt
            trf_final = trf - total_biaya if j_g == "Kotor" else trf

            jt_fmt = format_rupiah(jt_final)
            trf_fmt = format_rupiah(trf_final)

            st.text_input("Jumlah Transaksi (Rp)", value=jt_fmt, disabled=True)
            st.text_input("Jumlah Transfer (Rp)", value=trf_fmt, disabled=True)

            estimasi = timedelta(hours=3)
            waktu_selesai = (datetime.now(ZoneInfo("Asia/Jakarta")) + estimasi).strftime("%H:%M WIB")

            st.markdown("---")
            st.subheader("👨‍💼 Data Petugas")

            colA, colB = st.columns(2)
            with colA:
                petugas_nama = st.text_input("Nama Petugas", value="Thoriq")
            with colB:
                petugas_shift = st.selectbox("Shift Kerja", ["1 Shift", "Pagi", "Siang", "Malam"])

            if st.button("Generate WhatsApp Text"):
                teks_output = f"""
*TRANSAKSI NO. {transaksi_no} ({metode_transaksi.upper()})*
_______________________________
• Nama Nasabah : {nama}
• Kategori Nasabah : {jenis} ({kelas})
• Jenis Media Pencairan : {media}
• Produk : {produk}
• Rate Jual : {rt_str}
• Rate Untung : {ru_str}
• Nominal Transaksi : *{jt_fmt}*
• Biaya Nasabah Baru : Rp. {biaya_baru:,}
• Biaya Transfer Selain BCA : Rp. {biaya_transfer:,}
• Biaya Transaksi di Mesin EDC : Rp. {biaya_edc:,}
• Biaya Layanan QRIS By WhatsApp : Rp. {biaya_qris_wa:,}
_______________________________
Jumlah Transfer : *{trf_fmt}*
🕓 Estimasi Selesai: {waktu_selesai}

Petugas: {petugas_nama} ({petugas_shift})
"""
                st.code(teks_output, language="text")

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