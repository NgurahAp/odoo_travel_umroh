# Panduan Demo dan Validasi Manual Phase 4

Gunakan database demo khusus dan akun internal terpisah untuk Staff, Finance, Manager, serta System Administrator. Semua data bertanda `DEMO-` bersifat sintetis. Email `.example.test` tidak dapat menerima email nyata tanpa SMTP yang sengaja dikonfigurasi.

Untuk setiap langkah, simpan screenshot yang memperlihatkan breadcrumb/menu, record atau filter aktif, dan hasil akhirnya. Jangan memakai data pelanggan nyata.

## 1. Preflight lingkungan

| Peran | Navigasi dan input | Hasil yang diharapkan | Bukti |
|---|---|---|---|
| Administrator | Terminal: `docker compose ps`, lalu buka `http://localhost:8069` dan pilih database demo | Odoo dan PostgreSQL sehat; modul Travel Umroh terpasang versi Phase 4 | Screenshot status container, Apps/module, dan pemilih database |
| Administrator | Travel Umroh → Booking, cari `DEMO-` | Tepat `DEMO-DRAFT`, `DEMO-DP`, dan `DEMO-PAID` terlihat | Screenshot tiga baris dan statusnya |

## 2. Master dan kapasitas oleh Manager

| Peran | Navigasi dan input | Hasil yang diharapkan | Bukti |
|---|---|---|---|
| Manager | Travel Umroh → Paket; buka paket demo | Paket demo memiliki tepat tiga harga kamar: Quad, Triple, Double | Screenshot paket dan tiga harga |
| Manager | Travel Umroh → Keberangkatan; filter paket demo | Dua keberangkatan demo terlihat, lengkap dengan penerbangan, hotel, kuota, dan status | Screenshot daftar serta masing-masing tab transport/hotel |
| Manager | Reporting → Kapasitas Keberangkatan; pindah List, Pivot, Graph | Total, terpakai, dan sisa kuota konsisten; keberangkatan `DEMO-PAID` memakai dua kursi | Screenshot ketiga mode, terutama dua kursi terpakai |

## 3. Draft, Jamaah, dan Manifest oleh Staff

| Peran | Navigasi dan input | Hasil yang diharapkan | Bukti |
|---|---|---|---|
| Staff | Booking → buka `DEMO-DRAFT` | Status Quotation/Belum Bayar; participant, paket, keberangkatan, dan harga snapshot tampil | Screenshot header dan participant |
| Staff | Jamaah → buka Jamaah demo Draft | Status dokumen dan kelengkapan identitas terlihat; Staff hanya mengikuti aksi submit yang tersedia | Screenshot identitas sintetis dan status dokumen |
| Staff | Reporting → Manifest Jamaah; filter keberangkatan Draft | Manifest hanya berisi participant Travel yang sesuai dan list tidak bisa diedit langsung | Screenshot filter serta kolom Jamaah/NIK/paspor/status |

## 4. Booking DP dan sisa tagihan oleh Finance

| Peran | Navigasi dan input | Hasil yang diharapkan | Bukti |
|---|---|---|---|
| Finance | Booking → buka `DEMO-DP`, lalu smart button Invoice | Booking berstatus Sales Order dan pembayaran Travel `DP`; invoice DP posted/paid sesuai demo, sedangkan residual order belum lunas | Screenshot Booking, invoice, payment state, dan residual |
| Finance | Reporting → Booking & Penjualan; Group By Status Pembayaran | Grup DP berisi `DEMO-DP` dengan participant dan total yang benar | Screenshot list/pivot dengan grup DP |
| Finance | Reporting → Sisa Tagihan | Action invoice pelanggan standar Odoo terbuka; residual/payment state menjadi sumber kebenaran | Screenshot filter invoice dan residual |

## 5. Booking lunas dan kapasitas

| Peran | Navigasi dan input | Hasil yang diharapkan | Bukti |
|---|---|---|---|
| Finance | Booking → buka `DEMO-PAID` dan invoice | Semua invoice terkait posted/paid; status pembayaran Travel `Lunas` | Screenshot Booking dan daftar invoice |
| Manager | Keberangkatan demo Paid serta Reporting → Kapasitas Keberangkatan | Tepat dua kursi reserved untuk booking lunas | Screenshot kapasitas sebelum perubahan |
| Finance atau Manager | Reporting → Booking & Penjualan; buka List/Pivot/Graph dan kelompokkan paket/keberangkatan | Sales dan jumlah participant teragregasi tanpa transaksi Sales biasa | Screenshot tiga mode laporan |

## 6. Simulasi pembatalan dan refund sintetis

Jangan mengubah `DEMO-PAID`; buat Booking baru atau duplikat sintetis agar data referensi tetap tersedia.

| Peran | Navigasi dan input | Hasil yang diharapkan | Bukti |
|---|---|---|---|
| Staff | Booking → New; pilih pemesan sintetis, keberangkatan terbuka, tambah dua Jamaah, Confirm | Booking Sales Order belum bayar; kuota belum berkurang | Screenshot sebelum invoice |
| Finance | Buat/post invoice DP, bayar penuh; lanjut invoice final dan bayar | Setelah pembayaran DP kursi reserved bertambah dua; setelah final status `Lunas` | Screenshot invoice/payment dan kapasitas |
| Manager | Cancel Booking; isi alasan `DEMO manual refund` | Booking dibatalkan, alasan dan pelepasan kapasitas muncul di Chatter, reserved berkurang dua | Screenshot wizard, status, Chatter, kapasitas |
| Finance | Dari masing-masing invoice pelanggan awal pilih Credit Note/Reverse, post refund, register payment keluar | Booking menjadi `Refunded`; kapasitas tidak kembali ter-reservasi | Screenshot credit note, pembayaran refund, status akhir |

## 7. Seluruh menu Reporting

| Peran | Navigasi dan input | Hasil yang diharapkan | Bukti |
|---|---|---|---|
| Staff/Finance/Manager | Reporting → Booking & Penjualan | Ketiganya dapat membaca List/Pivot/Graph; list report tidak editable | Screenshot tiap peran atau matriks hasil |
| Staff/Finance/Manager | Reporting → Kapasitas Keberangkatan | Total/terpakai/sisa dapat dibaca dan diagregasi | Screenshot Pivot/Graph |
| Staff/Finance/Manager | Reporting → Status Dokumen | Grup Belum Lengkap/Menunggu Verifikasi/Terverifikasi konsisten dengan Jamaah | Screenshot Pivot/Graph |
| Staff/Finance/Manager | Reporting → Manifest Jamaah | Filter keberangkatan bekerja dan manifest read-only | Screenshot Manifest Jamaah terfilter |
| Finance/Manager | Reporting → Sisa Tagihan | Menu terlihat dan membuka customer invoice standar | Screenshot menu dan action |
| Staff | Cari menu Sisa Tagihan | Menu tidak terlihat | Screenshot menu Reporting Staff |
| System Administrator | Buka kelima menu Reporting, lalu Travel Umroh → Konfigurasi | Semua laporan termasuk Sisa Tagihan terlihat; master data dapat dikelola tanpa harus diberi role bisnis Travel | Screenshot menu Reporting, Konfigurasi, dan satu form master |

## 8. Regresi Sales biasa

| Peran | Navigasi dan input | Hasil yang diharapkan | Bukti |
|---|---|---|---|
| Pengguna Sales yang berwenang | Sales → Quotations → New; buat quotation biasa tanpa Keberangkatan/Participant Travel | Quotation berfungsi normal dan tidak muncul di Booking & Penjualan atau Manifest Jamaah | Screenshot Sales biasa serta hasil filter laporan Travel |

## 9. Negative permission dan business error

| Peran | Percobaan | Hasil yang diharapkan | Bukti |
|---|---|---|---|
| Staff | Membuat/mengubah invoice atau register payment | Ditolak oleh akses Accounting; bukan traceback | Screenshot pesan akses |
| Finance | Mengubah field Booking atau participant | Ditolak oleh ACL/server guard | Screenshot pesan akses |
| Staff | Mengonfirmasi Booking dengan Jamaah belum terverifikasi sesuai tahapan yang mewajibkan verifikasi/keberangkatan | Pesan bisnis berbahasa Indonesia menjelaskan dokumen belum terverifikasi | Screenshot pesan |
| Staff | Mengonfirmasi/membayar Booking melebihi sisa kuota | Operasi ditolak dan kapasitas tidak menjadi negatif | Screenshot pesan dan kapasitas |
| Manager/Admin | Koreksi Jamaah atau attachment yang sudah verified | Diizinkan, perubahan diaudit di Chatter; workflow integrity tetap berlaku | Screenshot sebelum/sesudah dan audit |

## 10. Cleanup aman

- Batalkan Booking sintetis tambahan melalui workflow dan simpan alasannya.
- Arsipkan master sintetis tambahan jika UI menyediakan Archive dan record tidak lagi dipakai.
- Jangan hapus database, PostgreSQL data, Docker volume, invoice posted, payment, credit note, atau data development.
- Biarkan tiga record kontrol `DEMO-DRAFT`, `DEMO-DP`, dan `DEMO-PAID` utuh untuk demo berikutnya.
