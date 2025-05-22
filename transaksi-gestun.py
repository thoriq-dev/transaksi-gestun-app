import streamlit as st
from datetime import datetime, timedelta

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
    return f"{int((1 - rate) * 1000) / 10}%"  # contoh: 0.975 → 2.5%

# --- Antarmuka Web Streamlit ---
st.title("🔢 Estimasi & Hitung Transaksi Gestun")

menu = st.sidebar.selectbox("Pilih Menu", ["Estimasi Transfer", "Hitung Nominal Transaksi"])

if menu == "Estimasi Transfer":
    st.header("🕒 Estimasi Waktu Transfer")
    layanan = st.selectbox("Pilih Layanan Transfer:", [
        "Normal", "Kilat", "Super Kilat", "Tidak ada tambahan biaya layanan"
    ])

    waktu_mulai = datetime.now()
    durasi = estimasi_durasi("Normal" if layanan == "Tidak ada tambahan biaya layanan" else layanan)
    waktu_selesai = estimasi_selesai(waktu_mulai, durasi)

    st.subheader("Hasil Estimasi")
    st.write(f"**Layanan Transfer:** {layanan}")
    st.write(f"**Waktu Mulai:** {waktu_mulai.strftime('%H:%M')}")
    st.write(f"**Perkiraan Selesai:** {waktu_selesai}")

elif menu == "Hitung Nominal Transaksi":
    st.header("💰 Hitung Nominal Transaksi")

    jenis = st.radio("Pilih Jenis Perhitungan:", ["Gesek Kotor", "Gesek Bersih"])

    rate_dict = {
        "2.5% (0.975)": 0.975,
        "2.6% (0.974)": 0.974,
        "3.5% (0.965)": 0.965,
        "4.7% (0.953)": 0.953,
    }
    rate_label = st.selectbox("Pilih Rate Jual:", list(rate_dict.keys()))
    rate = rate_dict[rate_label]

    nominal = st.number_input(
        f"Masukkan nominal {'transaksi' if jenis == 'Gesek Kotor' else 'transfer'} (Rp):",
        min_value=0,
        step=10000
    )

    biaya_opsi = {
        "Biaya administrasi nasabah baru (Rp10.000)": 10000,
        "Biaya layanan super kilat (Rp18.000)": 18000,
        "Biaya layanan kilat (Rp15.000)": 15000,
        "Biaya transfer beda bank (Rp10.000)": 10000,
        "Tidak ada tambahan biaya layanan": 0
    }
    pilihan_biaya = st.multiselect("Pilih Biaya Tambahan Layanan:", list(biaya_opsi.keys()))

    biaya_total = sum([biaya_opsi[b] for b in pilihan_biaya if "Tidak ada" not in b])
    layanan_transfer = "Normal"
    if "Biaya layanan super kilat" in " ".join(pilihan_biaya):
        layanan_transfer = "Super Kilat"
    elif "Biaya layanan kilat" in " ".join(pilihan_biaya):
        layanan_transfer = "Kilat"

    if st.button("Hitung Sekarang"):
        waktu_mulai = datetime.now()
        estimasi_selesai_transfer = estimasi_selesai(waktu_mulai, estimasi_durasi(layanan_transfer))

        st.subheader("📊 Hasil Perhitungan")
        st.write(f"**Jenis Perhitungan:** {jenis}")
        st.write(f"**Rate Jual:** {tampilkan_rate(rate)}")
        st.write(f"**Biaya Tambahan:** Rp {format_rupiah(biaya_total)}")
        st.write(f"**Estimasi Selesai Transfer:** {estimasi_selesai_transfer}")

        if jenis == "Gesek Kotor":
            nominal_transfer = int(nominal * rate - biaya_total)
            st.write(f"**Nominal Transaksi:** Rp {format_rupiah(nominal)}")
            st.write(f"**Nominal Transfer:** Rp {format_rupiah(nominal_transfer)}")
        else:
            nominal_transaksi = int((nominal + biaya_total) / rate)
            st.write(f"**Nominal Transfer:** Rp {format_rupiah(nominal)}")
            st.write(f"**Nominal Transaksi:** Rp {format_rupiah(nominal_transaksi)}")
