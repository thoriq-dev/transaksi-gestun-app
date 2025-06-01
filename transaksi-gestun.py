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
    return f"{int((1 - rate) * 1000) / 10}%"  # contoh: 0.975 -> 2.5%

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

# --- Antarmuka Web Streamlit ---
st.set_page_config(page_title="Estimasi & Hitung Gestun", layout="centered")
st.title("🔢 Hitung Nominal & Estimasi Transfer Gestun")

menu = st.sidebar.selectbox("Pilih Menu", [
    "Hitung Nominal Transaksi",
    "Pembagian Transaksi EDC"
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

    layanan_transfer = st.selectbox("Pilih Layanan Transfer:", [
        "Normal", "Kilat", "Super Kilat"
    ])

    biaya_tambahan_opsi = [k for k in biaya_opsi if "layanan kilat" not in k and "super kilat" not in k and "Tidak ada" not in k]
    biaya_pilihan = st.multiselect("Pilih Biaya Tambahan Lainnya:", biaya_tambahan_opsi)
    biaya_total = sum([biaya_opsi[b] for b in biaya_pilihan])

    if layanan_transfer == "Kilat":
        biaya_total += biaya_opsi["Biaya layanan kilat (Rp15.000)"]
    elif layanan_transfer == "Super Kilat":
        biaya_total += biaya_opsi["Biaya layanan super kilat (Rp18.000)"]

    if st.button("Hitung Sekarang"):
        waktu_mulai = datetime.now(ZoneInfo("Asia/Jakarta"))
        estimasi_selesai_transfer = estimasi_selesai(waktu_mulai, estimasi_durasi(layanan_transfer))

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.subheader("📊 Hasil Perhitungan")
            st.write(f"**➤Jenis Perhitungan:** {jenis}")
            st.write(f"**➤Rate Jual:** {tampilkan_rate(rate)}")
            st.write(f"**➤Biaya Tambahan Total:** {format_rupiah(biaya_total)}")
            if jenis == "Gesek Kotor":
                nominal_transfer = int(nominal * rate - biaya_total)
                st.write(f"**➤Nominal Transfer:** {format_rupiah(nominal_transfer)}")
                st.write(f"**➤Nominal Transaksi:** {format_rupiah(nominal)}")
            else:
                fee = int(nominal / rate - nominal)
                nominal_transaksi = nominal + fee + biaya_total
                st.write(f"**➤Nominal Transfer:** {format_rupiah(nominal)}")
                st.write(f"**➤Nominal Transaksi:** {format_rupiah(nominal_transaksi)}")
            st.write(f"**➤Waktu Transaksi:** {waktu_mulai.strftime('%H:%M')}")
            st.write(f"**➤Waktu Estimasi Transfer:** {estimasi_selesai_transfer}")

elif menu == "Pembagian Transaksi EDC":
    st.header("🧮 Pembagian Transaksi ke Mesin EDC")

    total_transaksi = st.number_input("Masukkan Total Transaksi (Rp)", min_value=0, step=1_000_000, format="%d")
    jumlah_mesin = st.number_input("Masukkan Jumlah Mesin EDC", min_value=1, max_value=20, step=1)

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
        for nama, nominal in pembagian:
            st.write(f"{nama}: {format_rupiah(nominal)}")
        if sisa > 0:
            st.warning(f"Sisa yang belum terbagi: {format_rupiah(sisa)}")
        else:
            st.success("Semua transaksi sudah terbagi ke mesin EDC.")
