# Panduan End-to-End Travel Umroh: Dari Database Kosong sampai Selesai

Panduan ini ditujukan untuk pengguna yang baru mengenal Odoo. Ikuti urutannya dari atas ke bawah. Setiap data di bawah bersifat **fiktif tetapi dibuat menyerupai data operasional**. Jangan mengganti data uji ini dengan NIK, paspor, email, atau nomor telepon pelanggan nyata.

Database manual yang dipakai:

- Nama: `travel_umroh_e2e_manual`
- Modul: `travel_umroh` versi `18.0.4.0.0`
- Kondisi awal: tanpa demo; master Travel, Jamaah, Booking, dan invoice pelanggan berjumlah nol
- URL login: [http://localhost:8069/web/login?db=travel_umroh_e2e_manual](http://localhost:8069/web/login?db=travel_umroh_e2e_manual)

Database lama tidak dipakai dalam panduan ini. Pastikan URL memuat parameter `db=travel_umroh_e2e_manual`, terutama jika browser pernah login ke database lain.

## 1. Gambaran paling sederhana

Anggap modul ini memiliki empat meja kerja yang saling menyerahkan pekerjaan:

1. **Manager** menyiapkan apa yang dijual: paket, jadwal, harga, pesawat, hotel, dan kuota.
2. **Staff** mencatat siapa yang berangkat dan membuat Booking.
3. **Finance** membuat invoice, menerima pembayaran, dan memproses refund.
4. **Manager** memverifikasi dokumen, mengizinkan keberangkatan, lalu menutup perjalanan.

Alur datanya adalah:

```text
Produk Jasa
    ↓
Paket ──→ Keberangkatan ──→ harga + penerbangan + hotel + kuota
                                  ↓
Kontak ──→ Profil Jamaah ──→ Booking ──→ Invoice DP ──→ Kursi reserved
                                  ↓                         ↓
                              Participant              Invoice pelunasan
                                  ↓                         ↓
                           Manifest Jamaah          Lunas / Refund
                                  └──────────────→ Berangkat → Selesai
```

Istilah yang sering tertukar:

- **Pemesan / Penanggung Jawab** adalah kontak yang membeli atau mengurus transaksi. Orang ini boleh tidak ikut berangkat.
- **Jamaah** adalah profil orang yang dapat menjadi peserta perjalanan.
- **Participant** adalah Jamaah yang dimasukkan ke satu Booking.
- **Booking** memakai mesin Sales Order Odoo, tetapi ditampilkan melalui menu Travel Umroh.
- **Invoice, pembayaran, dan credit note** tetap memakai Accounting standar Odoo sebagai sumber kebenaran.
- **Kursi belum reserved saat Booking di-Confirm.** Kursi baru reserved setelah invoice DP dibayar penuh.

## 2. Tujuan setiap role

| Role | Tujuan | Boleh melakukan | Tidak boleh melakukan |
|---|---|---|---|
| Administrator | Setup teknis awal | Mengatur perusahaan, produk, user, role, dan seluruh konfigurasi sistem | Jangan dipakai sebagai role operasional harian karena aksesnya terlalu luas |
| Staff | Menangani penjualan dan data Jamaah | Membuat/mengubah quotation Travel saat Draft/Sent, memilih pemesan, menambah participant, mengelola Jamaah sebelum verified, mengajukan dokumen, membaca master/laporan | Membuat invoice/pembayaran/refund, mengubah harga snapshot, mengoreksi Jamaah verified, mengubah Booking setelah Confirm |
| Finance | Menangani uang | Membaca Booking, membuat DP/final invoice, post invoice, register payment, membuat credit note/refund, membaca laporan dan sisa tagihan | Membuat atau mengubah Booking/participant, mengubah master, memverifikasi dokumen |
| Manager | Menjaga kontrol operasional | Semua kemampuan Staff dan Finance, CRUD master, membuka keberangkatan, verifikasi dokumen, koreksi terverifikasi yang diaudit, pembatalan setelah DP, tandai berangkat/selesai | Tidak boleh melewati aturan workflow seperti kuota, status dokumen, atau audit |

Role Travel bukan pembatas data berdasarkan salesperson. Staff, Finance, dan Manager dapat membaca semua Booking Travel yang berada pada perusahaan yang sama.

## 3. Maksud setiap phase

Phase adalah tahapan pembangunan software, bukan menu yang perlu dipilih oleh pengguna.

### Phase 1 — Fondasi dan master data

Tujuannya memastikan travel hanya menjual paket dan jadwal yang datanya jelas. Hasil Phase 1 adalah role Staff/Finance/Manager, maskapai, bandara, hotel, produk jasa, paket, keberangkatan, tiga harga kamar, penerbangan, akomodasi, dan kuota.

Checkpoint bisnis: Manager dapat membuka keberangkatan yang lengkap; Staff dan Finance hanya membaca master.

### Phase 2 — Jamaah dan Booking

Tujuannya mengubah pertanyaan “siapa membeli dan siapa yang berangkat?” menjadi data transaksi yang rapi. Satu pemesan boleh membiayai banyak Jamaah. Setiap Participant memperoleh satu harga snapshot dan satu baris Sales tersembunyi.

Checkpoint bisnis: Staff dapat membuat quotation dengan banyak participant dan meng-Confirm-nya tanpa mengurangi kuota.

### Phase 3 — Accounting, kuota, pembatalan, dan refund

Tujuannya menghubungkan Booking dengan uang dan kapasitas secara aman. Finance memakai invoice standar Odoo. Pembayaran penuh atas invoice DP memicu reservasi kursi tepat satu kali. Manager membatalkan Booking setelah DP dengan alasan, kursi dilepas, lalu Finance memproses credit note/refund.

Checkpoint bisnis: status `Belum Bayar → DP → Lunas/Refunded` berasal dari invoice, sedangkan kapasitas tidak pernah negatif.

### Phase 4 — Laporan, demo, dan hardening

Tujuannya membuat data Phase 1–3 dapat diaudit dan dipakai operasional: laporan Booking & Penjualan, kapasitas, status dokumen, manifest Jamaah, dan sisa tagihan. Phase ini juga memperkuat error bisnis, security, install/upgrade, dan regresi Sales biasa.

Checkpoint bisnis: setiap role melihat laporan yang sesuai dan angka laporan sama dengan transaksi sumbernya.

### Phase 5 — Portal Jamaah, masih ditunda

Phase 5 baru diperlukan jika pelanggan harus login sendiri untuk melihat Booking, itinerary, invoice, atau mengunggah dokumen dari portal. Untuk operasional internal yang seluruh inputnya dilakukan Staff/Finance/Manager, Phase 1–4 sudah cukup sebagai MVP back-office. Jangan mulai Phase 5 sebelum kebutuhan self-service pelanggan benar-benar diputuskan.

## 4. Data skenario semi-riil

### 4.1 Akun internal

Semua email memakai domain `.example.test`, sehingga tidak akan menjadi alamat pelanggan nyata.

| Nama | Login | Role Travel | Password lokal sementara |
|---|---|---|---|
| Nadia Putri | `nadia.staff@example.test` | Staff | `UmrohTest!2026` |
| Rizky Maulana | `rizky.finance@example.test` | Finance | `UmrohTest!2026` |
| Ahmad Fauzan | `ahmad.manager@example.test` | Manager | `UmrohTest!2026` |

Password di atas hanya untuk localhost. Jangan gunakan di staging atau production.

### 4.2 Master perjalanan

| Jenis | Data |
|---|---|
| Produk Jasa | Paket Umroh Reguler 10 Hari; Type `Service`; Invoice Policy `Ordered quantities`; Customer Taxes dikosongkan |
| Paket | Nama `Umroh Reguler 10 Hari`; kode `REG-10`; durasi `10`; produk sesuai baris di atas |
| Maskapai | Saudia; IATA `SV` |
| Bandara 1 | Soekarno-Hatta International Airport; `CGK`; Jakarta; Indonesia |
| Bandara 2 | King Abdulaziz International Airport; `JED`; Jeddah; Saudi Arabia |
| Bandara 3 | Prince Mohammad bin Abdulaziz International Airport; `MED`; Madinah; Saudi Arabia |
| Hotel 1 | Al Noor Makkah Hotel; Makkah; bintang 4; jarak 0,8 km |
| Hotel 2 | Rawdah Madinah Hotel; Madinah; bintang 4; jarak 0,6 km |
| Keberangkatan | Paket REG-10; 10 November 2026–19 November 2026; kuota 45; IDR |
| Harga | Quad Rp29.500.000; Triple Rp31.500.000; Double Rp34.500.000 |
| Flight pergi | SV-819; CGK T3 → JED T1; 10 November 2026 11:00–17:00 |
| Flight pulang | SV-820; MED T1 → CGK T3; 19 November 2026 02:00–15:30 |
| Akomodasi 1 | Al Noor Makkah Hotel; 10–14 November 2026 |
| Akomodasi 2 | Rawdah Madinah Hotel; 14–19 November 2026 |

### 4.3 Pemesan dan Jamaah

Pemesan utama adalah **Fajar Pratama** (`fajar.buyer@example.test`, `0812-1111-0000`). Ia mengurus transaksi tetapi **tidak ikut berangkat**. Ini sengaja dibuat untuk membuktikan bahwa Pemesan boleh berbeda dari Jamaah.

| Jamaah | NIK fiktif | Lahir | Gender | Paspor | Berlaku hingga | Telepon | Email | Kontak darurat |
|---|---|---|---|---|---|---|---|---|
| Siti Rahmawati | `3174015002700001` | Bandung, 10-02-1970 | Perempuan | `A1234567` | 30-06-2031 | `0812-1111-0001` | `siti.rahmawati@example.test` | Fajar Pratama / `0812-1111-0000` |
| Budi Santoso | `3174011505680002` | Jakarta, 15-05-1968 | Laki-laki | `B2345678` | 15-12-2030 | `0812-1111-0002` | `budi.santoso@example.test` | Fajar Pratama / `0812-1111-0000` |
| Aisyah Putri | `3174015208950003` | Depok, 12-08-1995 | Perempuan | `C3456789` | 20-03-2032 | `0812-1111-0003` | `aisyah.putri@example.test` | Fajar Pratama / `0812-1111-0000` |
| Dewi Lestari | `3174014504900004` | Bogor, 05-04-1990 | Perempuan | `D4567890` | 10-09-2031 | `0812-1111-0004` | `dewi.lestari@example.test` | Fajar Pratama / `0812-1111-0000` |

Untuk alamat, pakai data uji yang sama: `Jl. Contoh Operasional No. 10`, Jakarta Selatan, DKI Jakarta, `12345`, Indonesia.

Gunakan [file KTP uji](test-data/KTP-UJI.txt) dan [file paspor uji](test-data/PASPOR-UJI.txt) sebagai attachment. Isi file sengaja bukan dokumen identitas.

## 5. Persiapan oleh Administrator

### 5.1 Masuk ke database yang benar

1. Buka jendela Incognito.
2. Buka URL database di bagian awal panduan.
3. Pada database lokal baru, login awal biasanya `admin` / `admin`.
4. Pastikan menu Apps menampilkan modul Travel Umroh sebagai Installed.

Expected result: menu Travel Umroh tersedia dan belum ada record master/Booking/Jamaah.

### 5.2 Ubah perusahaan dan mata uang sebelum transaksi

1. Buka Settings → Users & Companies → Companies → My Company.
2. Ubah nama menjadi `PT Safar Amanah Nusantara`.
3. Pilih Country `Indonesia` dan Currency `IDR`.
4. Save.

Lakukan ini sebelum membuat transaksi. Mata uang perusahaan tidak boleh diubah setelah journal entry diposting.

Expected result: form Keberangkatan nantinya menampilkan IDR dan harga memakai simbol Rupiah.

### 5.3 Buat produk jasa

1. Buka Sales → Products → Products → New.
2. Isi nama `Paket Umroh Reguler 10 Hari`.
3. Set Product Type menjadi `Service`.
4. Pada bagian Sales, set Invoicing Policy menjadi `Ordered quantities`.
5. Kosongkan Customer Taxes agar angka skenario mudah dicocokkan.
6. Save.

Expected result: produk dapat dipilih dari form Paket Travel. Produk barang atau policy berdasarkan delivered quantities harus ditolak.

### 5.4 Buat tiga user role

Untuk setiap akun pada tabel 4.1:

1. Buka Settings → Users & Companies → Users → New.
2. Isi Name dan Email Address sesuai tabel.
3. Pada tab Access Rights, cari bagian **Travel Umroh**.
4. Pilih tepat satu role: Staff, Finance, atau Manager.
5. Save.
6. Dari menu Action/gear user, gunakan Change Password dan isi password lokal sementara.

Expected result:

- Nadia memperoleh akses Staff dan Sales yang diperlukan.
- Rizky memperoleh akses Finance/Invoicing.
- Ahmad memperoleh kemampuan Staff + Finance + Manager.
- Ketiga user adalah Internal User, bukan Portal User.

## 6. Phase 1 — Manager menyiapkan jualan

Login sebagai Ahmad Manager.

### 6.1 Buat master

1. Travel Umroh → Konfigurasi → Maskapai: buat Saudia.
2. Travel Umroh → Konfigurasi → Bandara: buat CGK, JED, dan MED.
3. Travel Umroh → Konfigurasi → Hotel: buat dua hotel.
4. Travel Umroh → Paket → New: isi data Paket pada tabel 4.2 dan pilih Produk Jasa yang sudah dibuat Admin.

Jika menu Konfigurasi tidak terlihat di bar atas, buka menu overflow/anak menu Travel Umroh. Menu ini memang hanya untuk Manager dan Administrator.

### 6.2 Buat dan buka keberangkatan

1. Travel Umroh → Keberangkatan → New.
2. Isi Paket, tanggal 10–19 November 2026, dan kuota 45.
3. Tab Harga: tambah Quad, Triple, dan Double beserta harga masing-masing.
4. Tab Penerbangan: tambah dua flight sesuai tabel.
5. Tab Akomodasi: tambah dua hotel sesuai tabel.
6. Save, lalu klik **Buka Keberangkatan**.

Expected result:

- Nama otomatis menyerupai `REG-10 — 10 Nov 2026`.
- Status berubah dari Draft menjadi Dibuka.
- Reserved Seats = 0 dan Remaining Seats = 45.
- Keberangkatan gagal dibuka jika salah satu harga Quad/Triple/Double belum ada.
- Akomodasi harus berada di antara tanggal keberangkatan dan kepulangan.

Checkpoint Phase 1: logout Manager, login Staff lalu Finance; keduanya dapat membaca Paket/Keberangkatan tetapi tidak dapat mengubah master atau membuka keberangkatan.

## 7. Phase 2 — Staff membuat Jamaah dan Booking

Login sebagai Nadia Staff.

### 7.1 Buat tiga Jamaah utama

Untuk Siti, Budi, dan Aisyah:

1. Travel Umroh → Jamaah → New.
2. Field paling atas bernama **Nama Jamaah / Kontak**. Klik dropdown, ketik nama, lalu pilih Create/Create and Edit. Ini normal: Jamaah memang ditautkan ke satu Contact Odoo.
3. Isi kontak, alamat, NIK, tempat/tanggal lahir, gender, paspor, dan kontak darurat dari tabel.
4. Upload file KTP uji dan file paspor uji.
5. Save lalu klik **Ajukan Dokumen**.

Expected result: status masing-masing berubah dari Belum Lengkap menjadi Menunggu Verifikasi. Pengajuan harus ditolak jika file KTP, nomor paspor, masa berlaku paspor, atau file paspor belum lengkap.

### 7.2 Manager memverifikasi dokumen

Login sebagai Ahmad Manager:

1. Travel Umroh → Jamaah.
2. Filter Menunggu Verifikasi.
3. Periksa tiap profil, lalu klik **Verifikasi Dokumen**.

Expected result: ketiga Jamaah berstatus Terverifikasi serta field Diverifikasi Oleh/Waktu Verifikasi terisi.

### 7.3 Staff membuat Booking utama

Login kembali sebagai Nadia Staff:

1. Travel Umroh → Booking → New.
2. Pada **Pemesan / Penanggung Jawab**, ketik `Fajar Pratama`, buat Contact baru, lalu isi email dan telepon pemesan.
3. Pilih keberangkatan REG-10 yang berstatus Dibuka. Paket Travel akan terisi otomatis.
4. Tab Participant → Add a line:
   - Siti Rahmawati — Quad — Rp29.500.000
   - Budi Santoso — Triple — Rp31.500.000
   - Aisyah Putri — Double — Rp34.500.000
5. Pastikan harga terisi otomatis, lalu Save.
6. Klik Confirm.

Expected result:

- Total sebelum pajak = Rp95.500.000.
- Booking berubah dari Quotation menjadi Sales Order.
- Status pembayaran Travel = Belum Bayar.
- Seat Reserved masih false; kapasitas tetap 0/45. Confirm bukan reservasi kursi.
- Participant dan keberangkatan terkunci untuk Staff setelah Confirm.

Checkpoint Phase 2: Fajar adalah Pemesan tetapi tidak muncul sebagai Participant. Tiga Jamaah muncul sebagai Participant dan masing-masing memakai harga snapshot sesuai tipe kamar.

## 8. Phase 3A — Finance menerima DP dan pelunasan

Login sebagai Rizky Finance.

### 8.1 Buat dan bayar invoice DP 30%

1. Travel Umroh → Booking → buka Booking utama.
2. Klik **Create Invoice**.
3. Pilih Down payment (percentage), isi `30%`, lalu Create Draft.
4. Buka invoice draft dan klik Confirm/Post.
5. Sebelum pembayaran, periksa bahwa kursi belum reserved.
6. Klik Register Payment, pilih jurnal Bank, metode Manual, dan bayar seluruh nilai DP.

Expected result:

- Nilai DP = Rp28.650.000.
- Setelah invoice diposting tetapi belum lunas, status Booking = DP dan kursi belum reserved.
- Setelah DP dibayar penuh, Seat Reserved = true.
- Keberangkatan menunjukkan Reserved Seats = 3 dan Remaining Seats = 42.
- Menekan proses pembayaran ulang tidak boleh menggandakan reservasi.

### 8.2 Buat dan bayar invoice final

1. Kembali ke Booking utama dan klik Create Invoice.
2. Pilih Regular invoice dan pastikan down payment dikurangkan.
3. Create Draft, Confirm/Post, lalu Register Payment penuh.

Expected result:

- Nilai invoice final = Rp66.850.000.
- Total invoice DP + final = Rp95.500.000.
- Status pembayaran Travel berubah menjadi Lunas.
- Reserved Seats tetap 3, tidak bertambah lagi ketika final invoice dibayar.

## 9. Phase 3B — Pembatalan setelah DP dan refund

Bagian ini membuktikan pembatalan terkontrol tanpa mengganggu Booking utama.

### 9.1 Staff membuat Booking kedua

Login sebagai Nadia Staff:

1. Buat Jamaah Dewi Lestari dari tabel, tetapi biarkan dokumennya Belum Lengkap.
2. Buat Booking baru dengan Pemesan Fajar, keberangkatan REG-10, dan satu Participant Dewi tipe Quad.
3. Confirm Booking.

Expected result: total Rp29.500.000; belum bayar; kapasitas masih 3 reserved.

### 9.2 Finance membayar DP Booking kedua

Login sebagai Rizky Finance:

1. Buat down payment percentage 20%.
2. Post invoice dan Register Payment penuh.

Expected result: DP Rp5.900.000; Booking berstatus DP; kapasitas menjadi 4 reserved dan 41 tersisa.

### 9.3 Manager membatalkan Booking

Login sebagai Ahmad Manager:

1. Buka Booking kedua.
2. Klik **Batalkan setelah DP**.
3. Isi alasan `Jamaah membatalkan karena alasan keluarga — skenario manual`.
4. Konfirmasi pembatalan.

Expected result: Booking berstatus Cancelled; Chatter menyimpan alasan dan pelepasan kursi; kapasitas kembali menjadi 3 reserved dan 42 tersisa.

### 9.4 Finance memproses refund

Login sebagai Rizky Finance:

1. Buka invoice DP Booking kedua.
2. Pilih Credit Note/Reverse, isi alasan `Refund pembatalan Booking manual`.
3. Buat dan Post credit note.
4. Register Payment pada credit note hingga residual nol.

Expected result: nilai credit note Rp5.900.000; invoice dan credit note sama-sama settled; status pembayaran Booking menjadi Refunded; kursi tidak kembali reserved.

## 10. Phase 3C — Manager menjalankan keberangkatan

Login sebagai Ahmad Manager:

1. Buka Keberangkatan REG-10.
2. Klik **Tandai Berangkat**.
3. Setelah status Berangkat, klik **Tandai Selesai**.

Expected result:

- Booking utama memiliki tiga participant reserved dan semuanya verified, sehingga keberangkatan dapat berjalan.
- Dewi tidak menghalangi keberangkatan karena Booking-nya sudah Cancelled dan kursinya tidak reserved.
- Status Keberangkatan berubah Dibuka → Berangkat → Selesai.
- Booking aktif mengikuti status Travel Berangkat lalu Selesai.

Uji negatif yang benar: jika salah satu Jamaah pada Booking aktif/reserved belum verified, **Tandai Berangkat** harus ditolak dan menyebut nama Jamaah. Confirm Booking sendiri tidak mensyaratkan dokumen verified.

## 11. Phase 4 — Laporan dan rekonsiliasi

### 11.1 Booking & Penjualan

Login dengan Staff, Finance, atau Manager:

1. Travel Umroh → Laporan → Booking & Penjualan.
2. Buka search dropdown.
3. Group By → Status Pembayaran.
4. Pindah antara List, Pivot, dan Graph.

Expected result: Booking utama berada di grup Lunas; Booking kedua berada di grup Refunded; jumlah participant dan total penjualan konsisten.

**Penting:** grup DP/Lunas tidak ditambahkan ke layar Invoicing umum. Layar Invoicing memakai status Accounting standar seperti Draft, Posted, Paid, dan Reversed. Grup status Travel berada di laporan Booking & Penjualan.

### 11.2 Kapasitas Keberangkatan

1. Travel Umroh → Laporan → Kapasitas Keberangkatan.
2. Periksa List, Pivot, dan Graph.

Expected result: kuota 45; reserved 3; remaining 42. Booking yang sudah dibatalkan tidak dihitung.

### 11.3 Status Dokumen

1. Travel Umroh → Laporan → Status Dokumen.
2. Group By → Status Dokumen.

Expected result: Siti, Budi, dan Aisyah berada di Terverifikasi; Dewi berada di Belum Lengkap.

### 11.4 Manifest Jamaah

1. Travel Umroh → Laporan → Manifest Jamaah.
2. Filter Booking Aktif dan Group By → Keberangkatan.

Expected result: manifest default hanya menampilkan participant Booking aktif; list read-only; data NIK, paspor, kamar, dokumen, pembayaran, dan reservasi dapat diperiksa.

### 11.5 Sisa Tagihan

1. Login Finance atau Manager.
2. Travel Umroh → Laporan → Sisa Tagihan.

Expected result: action Customer Invoices standar Odoo terbuka. Gunakan filter To Pay/In Payment/Overdue dan nilai residual Accounting. Menu ini tidak terlihat untuk Staff.

## 12. Checklist security manual

| Percobaan | Expected result |
|---|---|
| Staff membuka Booking confirmed | Dapat membaca; participant/keberangkatan terkunci; tombol Create Invoice tidak tersedia |
| Staff mencoba akses langsung invoice/payment | Ditolak hak akses Accounting tanpa traceback |
| Finance membuka Booking | Dapat membaca dan membuat invoice melalui workflow; perubahan field Booking/participant ditolak |
| Finance membuka Konfigurasi master | Tidak dapat membuat/mengubah master |
| Manager mengoreksi Jamaah verified | Diizinkan dan koreksi tercatat di Chatter |
| Staff mengoreksi Jamaah verified | Ditolak |
| Manager membatalkan setelah invoice DP posted | Wajib memakai wizard dan alasan; kursi dilepas satu kali |
| Staff/Finance mencoba pembatalan setelah DP | Ditolak |
| Manager menandai berangkat saat participant reserved belum verified | Ditolak dengan pesan bisnis, bukan traceback |
| Semua role membuka laporan Travel | Dapat membaca; report list khusus tidak dapat diedit langsung |

## 13. Checklist selesai keseluruhan

Pengujian end-to-end dinyatakan lolos bila semua poin berikut benar:

- [ ] Perusahaan memakai IDR sebelum transaksi.
- [ ] Role Staff, Finance, dan Manager menampilkan menu yang sesuai.
- [ ] Keberangkatan hanya bisa Dibuka setelah tiga harga kamar lengkap.
- [ ] Pemesan Fajar berbeda dari tiga Jamaah pada Booking utama.
- [ ] Confirm Booking tidak mengurangi kuota.
- [ ] Pembayaran penuh DP mereservasi tepat tiga kursi satu kali.
- [ ] Pembayaran final mengubah status menjadi Lunas tanpa menambah kursi.
- [ ] Pembatalan Booking kedua melepaskan satu kursi dan mencatat alasan.
- [ ] Credit note yang selesai mengubah status Booking kedua menjadi Refunded.
- [ ] Hanya participant aktif/reserved dengan dokumen verified yang boleh berangkat.
- [ ] Booking & Penjualan menunjukkan grup Lunas dan Refunded.
- [ ] Kapasitas menunjukkan 45 total, 3 reserved, 42 tersisa.
- [ ] Status Dokumen menunjukkan 3 Terverifikasi dan 1 Belum Lengkap.
- [ ] Manifest default tidak memasukkan Booking yang dibatalkan.
- [ ] Staff tidak dapat membuat invoice; Finance tidak dapat mengubah Booking.

Jika semua checkpoint lolos, Phase 1–4 telah tervalidasi sebagai satu alur back-office. Berhenti di sini sampai keputusan bisnis mengenai Portal Jamaah/Phase 5 dibuat.
