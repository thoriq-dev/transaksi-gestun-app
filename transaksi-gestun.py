import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+

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

# --- Setup UI Streamlit ---
st.set_page_config(page_title="Estimasi & Hitung Gestun", layout="centered")
st.title("🔢 Hitung Nominal & Estimasi Transfer Gestun")

menu = st.sidebar.selectbox("Pilih Menu", [
    "Hitung Nominal Transaksi",
    "Pembagian Transaksi EDC"
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

    # Konversi ke integer (tanpa titik)
    raw = st.session_state.nominal_input.replace(".", "")
    if raw.isdigit():
        nominal_int = int(raw)
    else:
        nominal_int = 0

    st.write(f"▶️ Nilai sebenarnya (tanpa format): {nominal_int}")

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
        # Waktu mulai & estimasi selesai
        waktu_mulai = datetime.now(ZoneInfo("Asia/Jakarta"))
        estimasi_selesai_transfer = estimasi_selesai(
            waktu_mulai, estimasi_durasi(layanan_transfer)
        )

        # Kita buat 3 kolom supaya hasilnya di-tengah
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
