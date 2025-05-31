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
    return f"{int(nominal):,}".replace(",", ".")

def tampilkan_rate(rate):
    return f"{int((1 - rate) * 1000) / 10}%"  # contoh: 0.975 -> 2.5%

def hitung_fee(jenis, nominal, rate):
    if jenis == "Gesek Kotor":
        return int(nominal * (1 - rate))
    else:
        return int(nominal / rate - nominal)

# --- Antarmuka Web Streamlit ---
st.set_page_config(page_title="Estimasi & Hitung Gestun", layout="centered")
st.title("🔢 Hitung Nominal & Estimasi Transfer Gestun")

menu = st.sidebar.selectbox("Pilih Menu", [
    "Hitung Nominal Transaksi",
    "Estimasi Transfer",
    "Perhitungan Lengkap Gestun (MDR)"
])

if menu == "Hitung Nominal Transaksi":
    st.header("💰 Hitung Nominal Transaksi")

    jenis = st.radio("Pilih Jenis Perhitungan:", ["Gesek Kotor", "Gesek Bersih"])

    rate_dict = {
        "2.5% (0.975) Visa & Master Card": 0.975,
        "2.6% (0.974) Visa & Master Card": 0.974,
        "3.5% (0.965) BCA Card": 0.965,
        "4.7% (0.953) AMEX": 0.953,
    }
    rate_label = st.selectbox("Pilih Rate Jual:", list(rate_dict.keys()))
    rate = rate_dict[rate_label]

    nominal = st.number_input(
        f"Masukkan nominal {'transaksi' if jenis == 'Gesek Kotor' else 'transfer'} (Rp):",
        min_value=0,
        step=10000
    )

    # Fee Info
    if nominal > 0:
        fee = hitung_fee(jenis, nominal, rate)
        st.info(f"📌 Fee {tampilkan_rate(rate)} dari Rp {format_rupiah(nominal)} adalah Rp {format_rupiah(fee)}")

    biaya_opsi = {
        "Biaya administrasi nasabah baru (Rp10.000)": 10000,
        "Biaya layanan super kilat (Rp18.000)": 18000,
        "Biaya layanan kilat (Rp15.000)": 15000,
        "Biaya transfer beda bank (Rp10.000)": 10000,
        "Tidak ada tambahan biaya layanan": 0
    }

    # Batasi hanya satu layanan kilat/super kilat
    layanan_transfer = st.selectbox("Pilih Layanan Transfer:", [
        "Normal", "Kilat", "Super Kilat"
    ])

    # Biaya tambahan selain layanan
    biaya_tambahan_opsi = [k for k in biaya_opsi if "layanan kilat" not in k and "super kilat" not in k and "Tidak ada" not in k]
    biaya_pilihan = st.multiselect("Pilih Biaya Tambahan Lainnya:", biaya_tambahan_opsi)
    biaya_total = sum([biaya_opsi[b] for b in biaya_pilihan])

    # Tambah biaya dari layanan transfer
    if layanan_transfer == "Kilat":
        biaya_total += biaya_opsi["Biaya layanan kilat (Rp15.000)"]
    elif layanan_transfer == "Super Kilat":
        biaya_total += biaya_opsi["Biaya layanan super kilat (Rp18.000)"]

    if st.button("Hitung Sekarang"):
        waktu_mulai = datetime.now(ZoneInfo("Asia/Jakarta"))
        estimasi_selesai_transfer = estimasi_selesai(waktu_mulai, estimasi_durasi(layanan_transfer))

        # Menampilkan hasil di tengah dengan 3 kolom, kolom tengah paling besar
        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            st.subheader("📊 Hasil Perhitungan")
            st.write(f"**➤Jenis Perhitungan:** {jenis}")
            st.write(f"**➤Rate Jual:** {tampilkan_rate(rate)}")
            st.write(f"**➤Fee (tanpa biaya tambahan):** Rp {format_rupiah(fee)}")
            st.write(f"**➤Biaya Tambahan Total:** Rp {format_rupiah(biaya_total)}")
            st.write(f"**➤Estimasi Selesai Transfer:** {estimasi_selesai_transfer}")

            if jenis == "Gesek Kotor":
                nominal_transfer = int(nominal * rate - biaya_total)
                st.write(f"**➤Nominal Transaksi:** Rp {format_rupiah(nominal)}")
                st.write(f"**➤Nominal Transfer (setelah biaya):** Rp {format_rupiah(nominal_transfer)}")
            else:
                fee = int(nominal / rate - nominal)
                nominal_transaksi = nominal + fee + biaya_total
                st.write(f"**➤Nominal Transfer:** Rp {format_rupiah(nominal)}")
                st.write(f"**➤Nominal Transaksi:** Rp {format_rupiah(nominal_transaksi)}")

elif menu == "Estimasi Transfer":
    st.header("🕒 Estimasi Waktu Transfer")
    layanan = st.selectbox("Pilih Layanan Transfer:", ["Normal", "Kilat", "Super Kilat"])

    waktu_mulai = datetime.now(ZoneInfo("Asia/Jakarta"))
    durasi = estimasi_durasi(layanan)
    waktu_selesai = estimasi_selesai(waktu_mulai, durasi)

    st.subheader("Hasil Estimasi")
    st.write(f"**➤Layanan Transfer:** {layanan}")
    st.write(f"**➤Waktu Mulai:** {waktu_mulai.strftime('%H:%M')}")
    st.write(f"**➤Perkiraan Selesai:** {waktu_selesai}")

elif menu == "Perhitungan Lengkap Gestun (MDR)":
    st.header("📋 Perhitungan Lengkap Gestun (MDR Otomatis)")

    # Input data
    jenis = st.radio("Pilih Jenis Perhitungan:", ["Gesek Kotor", "Gesek Bersih"])
    bank_edc = st.selectbox("Pilih Bank EDC:", ["BNI", "BCA", "BRI"])
    status_kartu = st.radio("Status Kartu:", ["On Us", "Off Us"])
    nominal = st.number_input("Masukkan Nominal Transaksi (Rp):", min_value=0, step=10000)
    rate_jual = st.slider("Pilih Rate Jual (%):", min_value=2.0, max_value=9.0, step=0.1)  # Slider interaktif

    # MDR Rates
    mdr_rates = {
        "BNI": {"On Us": 1.65, "Off Us": 1.85},
        "BCA": {"On Us": 1.5, "Off Us": 2.0},
        "BRI": {"On Us": 1.5, "Off Us": 1.8},
    }

    if nominal > 0:
        mdr = mdr_rates[bank_edc][status_kartu]
        fee = nominal * (rate_jual / 100)
        potongan_mdr = nominal * (mdr / 100)
        dana_masuk = nominal - potongan_mdr

        if jenis == "Gesek Kotor":
            dana_ke_nasabah = nominal - fee
        else:  # Gesek Bersih
            dana_ke_nasabah = nominal

        laba_kotor = dana_masuk - dana_ke_nasabah

        st.subheader("📊 Hasil Perhitungan")
        st.write(f"**➤Bank EDC:** {bank_edc}")
        st.write(f"**➤Status Kartu:** {status_kartu}")
        st.write(f"**➤MDR:** {mdr}%")
        st.write(f"**➤Rate Jual:** {rate_jual}%")
        st.write(f"**➤Nominal Transaksi:** Rp {format_rupiah(nominal)}")
        st.write(f"**➤Fee dari Rate Jual:** Rp {format_rupiah(fee)}")
        st.write(f"**➤Potongan MDR:** Rp {format_rupiah(potongan_mdr)}")
        st.write(f"**➤Dana Masuk ke Rekening:** Rp {format_rupiah(dana_masuk)}")
        st.write(f"**➤Dana Diberikan ke Nasabah:** Rp {format_rupiah(dana_ke_nasabah)}")
        st.success(f"💸 Laba Kotor: Rp {format_rupiah(laba_kotor)}")
