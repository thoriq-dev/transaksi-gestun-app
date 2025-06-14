import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+
import streamlit.components.v1 as components


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

# Helper Format Nomor Transaksi
def fmt_heading(t): return f'*{t}*' if bold_headings else t

# --- App Config ---
st.set_page_config(page_title="Input Data Transaksi Gestun", layout="centered")

menu = st.sidebar.selectbox("Pilih Menu", [
    "Hitung Nominal Transaksi",
    "Pembagian Transaksi EDC",
    "Input Data Transaksi Gestun"
])

# ===============================
# MENU 1: HITUNG NOMINAL TRANSAKSI
# ===============================
if menu == "Hitung Nominal Transaksi":
    st.header("💰 Hitung Nominal Transaksi")

    # Pilihan jenis & rate
    jenis = st.radio("Pilih Jenis Perhitungan:", ["Gesek Kotor", "Gesek Bersih"])
    rate_dict = {
        "2.5% (0.975) Visa & Master Card": 0.975,
        "2.6% (0.974) Visa & Master Card": 0.974,
        "3.5% (0.965) BCA Card": 0.965,
        "4.7% (0.953) AMEX": 0.953,
    }
    rate_label = st.selectbox("Pilih Rate Jual:", list(rate_dict.keys()))
    rate = rate_dict[rate_label]

    # --- Callback untuk memformat input secara real-time ---
    def format_nominal():
        txt = st.session_state.nominal_input
        digits_only = "".join([c for c in txt if c.isdigit()])
        if digits_only:
            st.session_state.nominal_input = "{:,}".format(int(digits_only)).replace(",", ".")
        else:
            st.session_state.nominal_input = ""

    # Inisialisasi session_state (hanya sekali)
    if "nominal_input" not in st.session_state:
        st.session_state.nominal_input = ""

    # Text input yang memanggil callback format_nominal
    st.text_input(
        label=f"Masukkan nominal {'transaksi' if jenis == 'Gesek Kotor' else 'transfer'} (Rp):",
        key="nominal_input",
        on_change=format_nominal,
    )

    # <<–– Blok konversi harus tetap ada ––>>
    raw = st.session_state.nominal_input.replace(".", "")
    if raw.isdigit():
        nominal_int = int(raw)
    else:
        nominal_int = 0

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

    # --- Tombol Hitung Sekarang (harus di dalam blok ini) ---
    if st.button("Hitung Sekarang"):
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

# =================================
# MENU 2: PEMBAGIAN TRANSAKSI EDC
# =================================
elif menu == "Pembagian Transaksi EDC":
    st.header("🧮 Pembagian Transaksi ke Mesin EDC")

    total_transaksi = st.number_input(
        "Masukkan Total Transaksi (Rp)", min_value=0, step=1_000_000, format="%d"
    )
    jumlah_mesin = st.number_input(
        "Masukkan Jumlah Mesin EDC", min_value=1, max_value=20, step=1
    )

    st.subheader("Input Detail Setiap Mesin EDC")
    mesin_edc = []
    for i in range(jumlah_mesin):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            nama = st.text_input(f"Nama Mesin EDC {i+1}", value=f"EDC {i+1}", key=f"nama_{i}")
        with col2:
            batas = st.number_input(f"Batas Maks (Rp)", min_value=0, step=1_000_000, key=f"batas_{i}")
        with col3:
            prioritas = st.number_input(f"Prioritas", min_value=1, max_value=jumlah_mesin, key=f"prio_{i}")
        mesin_edc.append({
            'nama': nama,
            'batas': batas,
            'prioritas': prioritas
        })

    if st.button("Hitung Pembagian"):
        pembagian, sisa = hitung_pembagian_edc_prioritas(total_transaksi, mesin_edc)
        st.subheader("Hasil Pembagian:")
        for nama_mesin, nominal_edc in pembagian:
            st.write(f"{nama_mesin}: {format_rupiah(nominal_edc)}")
        if sisa > 0:
            st.warning(f"Sisa yang belum terbagi: {format_rupiah(sisa)}")
        else:
            st.success("Semua transaksi sudah terbagi ke mesin EDC.")

# =============================================
# MENU 3: INPUT DATA TRANSAKSI GESTUN
# =============================================
elif menu == "Input Data Transaksi Gestun":
    st.title("Form Input Data Transaksi Gestun")

    # Toggle formatting
    bold_headings = st.sidebar.checkbox("Bold Headings", True)
    italic_values = st.sidebar.checkbox("Italic Values", False)
    bold_values   = st.sidebar.checkbox("Bold Values", False)
    
    # --- Input lain di dalam form ---
    with st.form(key="form3"):
        transaksi_no = st.text_input("No. Transaksi")
        nama         = st.text_input("Nama Nasabah")
        jenis        = st.selectbox("Jenis Nasabah", ["Langganan", "Baru"])
        kelas        = st.selectbox("Kelas Nasabah", [
                          "Non Member", "Member Gold",
                          "Member Platinum", "Member Anggota Koperasi"
                        ])
        j_g    = st.radio("Jenis Gestun", ["Kotor", "Bersih"])
        metode = st.selectbox("Metode Gestun", ["Konven", "Online"])
        lay    = st.selectbox("Jenis Layanan Transfer", ["Normal", "Kilat", "Super Kilat"])
        prod    = st.text_input("Produk & Sub Produk")
        ket    = st.text_area("Keterangan Layanan", height=80)
        submit = st.form_submit_button("Generate WhatsApp Text")

# --- Formatted numeric inputs (thousands separator) – outside form ---
    rt_type = st.selectbox("Tipe Rate Jual", ["%", "Rp"])
    label   = "Rate Jual (%)" if rt_type == "%" else "Rate Jual (Rp)"
    if rt_type == "Rp":
        rt_str_raw = st.text_input(
            label, key="rt_rp_str",
            on_change=format_rupiah_input,
            args=("rt_rp_str",)
        )
        # parse integer, lalu format ulang
        raw = st.session_state["rt_rp_str"].replace(".", "")
        rt_val = int(raw) if raw.isdigit() else 0
        rt_str = format_rupiah(rt_val)
    else:
        rt_percent = st.number_input(
            label, min_value=0.0, max_value=100.0,
            step=0.1, format="%.2f"
        )
        rt_str = f"{rt_percent:.2f}%"
    bl_str = st.text_input(
        "Biaya Layanan (Rp)",
        key="bl_str",
        on_change=format_rupiah_input,
        args=("bl_str",)
    )
    jt_str = st.text_input(
        "Jumlah Transaksi (Rp)",
        key="jt_str",
        on_change=format_rupiah_input,
        args=("jt_str",)
    )
    trf_str = st.text_input(
        "Jumlah Transfer (Rp)",
        key="trf_str",
        on_change=format_rupiah_input,
        args=("trf_str",)
    )

    # parse ke integer
    raw_jt = jt_str.replace(".", "")
    raw_bl = bl_str.replace(".", "")
    raw_tr = trf_str.replace(".", "")

    jt = int(raw_jt) if raw_jt.isdigit() else 0
    bl = int(raw_bl) if raw_bl.isdigit() else 0
    trf = int(raw_tr) if raw_tr.isdigit() else 0


    # --- Setelah submit, bangun output ---
    if submit:
        jt_fmt  = format_rupiah(jt)
        bl_fmt  = format_rupiah(bl)
        trf_fmt = format_rupiah(trf)

        def fmt_heading(txt):
            return f"*{txt}*" if bold_headings else txt

        def fmt_value(txt):
            if bold_values:   txt = f"*{txt}*"
            if italic_values: txt = f"_{txt}_"
            return txt

        bullet = "•"
        sep    = "________"

        teks_output = f"""
{fmt_heading(f"TRANSAKSI NO. {transaksi_no}")}
{fmt_heading('DATA NASABAH')}
   {bullet}Nama Nasabah : {fmt_value(nama)}
   {bullet}Jenis Nasabah : {fmt_value(jenis)}
   {bullet}Kelas Nasabah : {fmt_value(kelas)}
{sep}
{fmt_heading('DATA TRANSAKSI')}
   {bullet}Jenis Gestun : {fmt_value(j_g)}
   {bullet}Metode Gestun : {fmt_value(metode)}
   {bullet}Jenis Layanan Transfer: {fmt_value(lay)}
   {bullet}Produk & Sub Produk : {fmt_value(prod)}
   {bullet}Rate Jual : {fmt_value(rt_str)}
{sep}
{fmt_heading('RANGKUMAN BIAYA DAN TRANSAKSI')}
   {bullet}Jumlah Transaksi : {fmt_value(jt_fmt)}
   {bullet}Biaya Layanan : {fmt_value(bl_fmt)}
   {bullet}Keterangan Layanan : {fmt_value(ket)}
{sep}
{fmt_heading(f"Jumlah Transfer : {trf_fmt}")}
"""
        st.text_area("Hasil (copyable ke WhatsApp):", teks_output, height=550)