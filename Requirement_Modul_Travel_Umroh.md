# Dokumen Kebutuhan Sistem: Modul Travel Umroh (Odoo 18)

## 1. Tujuan Utama
Sistem ini dibutuhkan oleh tim operasional untuk mempermudah pendaftaran jamaah umroh, mengelola pilihan paket perjalanan, serta mengatur data pendukung seperti jadwal pesawat dan pilihan hotel agar tidak diketik ulang setiap kali ada pendaftaran.

---

## 2. Kebutuhan Data Master (Referensi Sistem)
Sebelum membuat paket umroh, sistem harus menyediakan menu khusus agar admin bisa memasukkan data referensi berikut:

* **Daftar Maskapai Penerbangan:**
  * Nama Maskapai (Contoh: Saudia Airlines, Garuda Indonesia).
  * Terminal Keberangkatan & Kedatangan.
  * *Catatan user:* Data ini harus bisa dipilih nanti saat membuat paket umroh.

* **Daftar Hotel / Penginapan:**
  * Nama Hotel.
  * Lokasi Hotel (Makkah / Madinah).
  * Bintang/Rating Hotel (Bintang 3, 4, atau 5).
  * Jarak ke Masjid (opsional, sebagai info ke jamaah).

---

## 3. Kebutuhan Manajemen Paket Umroh
Tim produk/marketing membutuhkan satu formulir khusus untuk merancang penawaran paket umroh yang akan dijual ke jamaah.

* **Informasi Utama Paket:**
  * Nama Paket (Contoh: Paket Umroh Ramadhan, Paket Reguler 9 Hari).
  * Tanggal Keberangkatan dan Tanggal Kepulangan.
  * Total Kuota/Jumlah Seat yang tersedia.

* **Fasilitas Paket (Diambil dari Data Master):**
  * Pilihan Maskapai yang digunakan.
  * Pilihan Hotel di Makkah.
  * Pilihan Hotel di Madinah.

* **Pengaturan Harga Paket:**
  * Harga harus bisa dibedakan berdasarkan jenis kamar yang dipilih jamaah nantinya, misalnya:
    * Harga Kamar *Quad* (1 kamar 4 orang).
    * Harga Kamar *Triple* (1 kamar 3 orang).
    * Harga Kamar *Double* (1 kamar 2 orang).

---

## 4. Kebutuhan Data Peserta (Jamaah)
Saat admin mendaftarkan jamaah, formulir data diri harus dibuat ringkas, tidak bertele-tele, namun mencakup informasi legal yang wajib untuk pembuatan visa dan tiket.

* **Biodata Inti:**
  * Nama Lengkap (Sesuai KTP/Paspor).
  * NIK KTP.
  * Tempat dan Tanggal Lahir (Sistem otomatis menghitung Umur saat ini).
  * Jenis Kelamin.

* **Informasi Kontak:**
  * Nomor WhatsApp / Telepon aktif.
  * Alamat Domisili Singkat.

* **Dokumen Perjalanan:**
  * Nomor Paspor (Bisa dikosongkan jika jamaah belum membuat paspor).

* **Kontak Darurat:**
  * Nama Keluarga/Ahli Waris yang bisa dihubungi & Nomor Teleponnya.

---

## 5. Alur Transaksi & Pendaftaran (Pemesanan)
Ini adalah layar utama yang akan dipakai oleh tim Sales/Admin pendaftaran setiap harinya.

* **Proses Pembuatan Pesanan:**
  * Admin memilih **Paket Umroh** yang ingin dibeli oleh jamaah.
  * Admin memasukkan **Data Peserta** (bisa memilih dari data jamaah yang sudah pernah daftar, atau membuat data baru).
  * Admin memilih tipe kamar untuk jamaah tersebut (Quad/Triple/Double).

* **Perhitungan Harga Otomatis:**
  * Setelah memilih tipe kamar, sistem otomatis memunculkan Total Tagihan sesuai harga yang sudah diatur di dalam Paket Umroh.

* **Status Dokumen Pendaftaran:**
  * Formulir pendaftaran harus memiliki penanda status perjalanan jamaah, seperti: *Draft (Baru Tanya-tanya) -> DP/Bayar Sebagian -> Lunas -> Berangkat -> Selesai*.
