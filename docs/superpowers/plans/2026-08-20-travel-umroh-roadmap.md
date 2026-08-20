# Roadmap Implementasi Modul Travel Umroh Odoo 18

Tanggal: 20 Agustus 2026  
Status: disetujui untuk perencanaan implementasi  
PRD sumber: `Requirement_Modul_Travel_Umroh.md`  
Technical design: `docs/superpowers/specs/2026-08-20-travel-umroh-odoo-18-design.md`

## 1. Fungsi Dokumen

Roadmap ini menentukan urutan implementasi agar AI mengerjakan bagian kecil yang dapat diuji dan didemokan. Dokumen ini tidak mengulang seluruh requirement atau desain teknis.

Tiga lapis dokumen yang menjadi source of truth:

1. `Requirement_Modul_Travel_Umroh.md`: kebutuhan produk atau PRD ringkas—apa yang dibutuhkan dan mengapa.
2. `docs/superpowers/specs/2026-08-20-travel-umroh-odoo-18-design.md`: technical design—model, workflow, security, dan keputusan arsitektur.
3. `docs/superpowers/plans/*.md`: implementation plan—urutan file, test, command, dan bukti selesai.

Bila terjadi konflik, keputusan bisnis terbaru pada PRD menang untuk tujuan produk, sedangkan technical design menang untuk detail implementasi yang tidak diatur PRD. Perubahan scope harus memperbarui dokumen sumber sebelum code diubah.

## 2. Aturan Eksekusi untuk AI

Setiap fase harus mengikuti siklus berikut:

1. Baca PRD, technical design, roadmap, dan plan fase aktif.
2. Kerjakan hanya scope fase aktif.
3. Untuk setiap behavior: tulis test gagal, jalankan untuk membuktikan gagal, implementasikan minimum code, lalu jalankan test sampai lulus.
4. Jalankan seluruh test modul dan install/upgrade check pada akhir fase.
5. Review perubahan terhadap acceptance criteria fase.
6. Berhenti di checkpoint dan laporkan bukti test sebelum masuk fase berikutnya.
7. Buat plan detail fase berikutnya berdasarkan kondisi code aktual, bukan hanya asumsi awal.

Tidak boleh menambahkan WhatsApp, payment gateway, waitlist, room allocation, multi-company, custom OWL dashboard, atau self-registration publik tanpa perubahan scope yang disetujui.

## 3. Urutan Fase

### Phase 0 — Environment dan Desain

Status: selesai.

Hasil:

- Odoo 18 Community dan PostgreSQL 15 berjalan melalui Docker Compose.
- Folder `addons/` terpasang ke `/mnt/extra-addons`.
- Keputusan produk dan technical design sudah ditulis.

Checkpoint:

- Odoo dapat diakses di `http://localhost:8069`.
- Database development dapat dibuka.
- `docker compose ps` menunjukkan service database sehat dan Odoo berjalan.

### Phase 1 — Module Foundation dan Master Data

Tujuan: menghasilkan add-on Odoo yang dapat di-install dan menyediakan konfigurasi dasar paket serta keberangkatan.

Scope:

- Scaffold add-on `travel_umroh`.
- Groups Travel Staff, Travel Finance, dan Travel Manager.
- Master airline, airport, dan hotel.
- Package dan relasi service product Odoo.
- Departure, kuota, mata uang, dan harga Quad/Triple/Double.
- Flight dan accommodation itinerary.
- Menu, list, form, dan search view standar Odoo.
- Constraint, ACL, dan automated tests untuk scope ini.

Tidak termasuk:

- Profil jamaah.
- Booking atau perubahan `sale.order`.
- Reservasi seat dan pembayaran.
- Portal.

Exit criteria:

- Modul dapat di-install dan di-upgrade tanpa error.
- Manager dapat membuat package dan membuka departure yang memiliki tiga harga lengkap.
- Data tanggal, harga, kuota, flight, dan accommodation yang tidak valid ditolak.
- Staff dan Finance hanya dapat membaca master; Manager dapat mengelolanya.
- Seluruh automated test Phase 1 lulus.

Plan detail: `docs/superpowers/plans/2026-08-20-phase-1-foundation-master-data.md`.

### Phase 2 — Jamaah dan Booking/Quotation

Tujuan: Staff dapat membuat quotation travel multi-participant dengan harga otomatis dan snapshot yang aman.

Scope:

- Profil `travel.jamaah` one-to-one dengan `res.partner`.
- Identitas, kontak darurat, dokumen KTP/paspor, dan status verifikasi.
- Perluasan `sale.order` sebagai booking travel.
- `travel.booking.participant`.
- Satu participant menghasilkan satu `sale.order.line` service product.
- Harga otomatis berdasarkan departure dan room type.
- Snapshot harga, refresh saat draft, dan penguncian setelah konfirmasi.
- Hak akses Staff/Finance/Manager untuk jamaah dan booking.
- Form Booking, Jamaah, smart fields, chatter, dan tests.

Exit criteria:

- Staff dapat membuat quotation dengan satu pemesan dan beberapa participant.
- Total quotation sama dengan jumlah snapshot harga participant.
- Konfirmasi Sales Order tidak mereservasi seat.
- Staff tidak dapat mengubah harga atau participant setelah konfirmasi.
- Manager dapat melakukan koreksi dengan audit chatter.
- Test model, workflow, dan security Phase 2 lulus.

### Phase 3 — DP, Accounting, Kuota, Cancellation, dan Refund

Tujuan: menghubungkan booking ke flow accounting Odoo dan menjaga kuota secara aman.

Scope:

- Computed travel payment state dari invoice, residual, dan credit note.
- Down payment invoice standar Odoo.
- Reservasi seat setelah invoice DP benar-benar lunas.
- Concurrency guard dan idempotency reservasi.
- Pencegahan overbooking.
- Pelunasan melalui invoice standar.
- Cancellation setelah DP oleh Manager.
- Pelepasan seat idempotent.
- Credit Note/refund standar Odoo.
- Workflow departure `departed`/`done` dan gate dokumen verified.
- Integration dan security tests accounting.

Exit criteria:

- Draft quotation dan Sales Order terkonfirmasi belum mengurangi kuota.
- DP lunas mengurangi kuota tepat satu kali.
- Dua transaksi bersamaan tidak dapat melewati kuota.
- Pembatalan melepas seat tepat satu kali.
- Payment state sesuai invoice/payment/credit note aktual dan tidak dapat diedit manual.
- Flow quotation sampai refund lulus integration tests.

### Phase 4 — Reporting, Demo Data, dan Hardening Internal

Tujuan: membuat back-office internal siap dipresentasikan sebagai studi kasus.

Scope:

- Search, list, pivot, dan graph view operasional.
- Booking per departure dan penggunaan kuota.
- Status dokumen dan pembayaran.
- Penjualan per package/departure.
- Manifest jamaah memakai view/report standar yang paling sederhana.
- Demo data terkontrol.
- End-to-end acceptance tests.
- Review hak akses, error message, audit trail, install, dan upgrade.
- Dokumentasi demo flow dan developer setup.

Exit criteria:

- Seluruh acceptance criteria fase internal pada technical design terpenuhi.
- Demo dapat dijalankan dari package sampai booking lunas dan refund.
- Database tanpa demo data tidak mendapat record contoh.
- Semua test lulus dan tidak ada error install/upgrade.

### Phase 5 — Portal Jamaah

Tujuan: jamaah dapat mengakses data yang terkait dengannya tanpa akses backend.

Scope:

- Portal routes dan QWeb templates.
- Portal booking, itinerary, quotation, dan invoice yang relevan.
- Upload dokumen oleh partner terkait.
- Update terbatas sebelum dokumen verified.
- Record rules dan server authorization portal.
- Portal integration dan negative security tests.

Exit criteria:

- Portal hanya membaca record milik atau tanggung jawab partner terkait.
- Portal tidak dapat memverifikasi dokumen, mengubah harga, pembayaran, atau status internal.
- Percobaan direct URL/RPC ke record lain ditolak.
- Seluruh portal tests lulus.

## 4. Dependency Antar Fase

```text
Phase 0: Environment + Design
              |
              v
Phase 1: Foundation + Master Data
              |
              v
Phase 2: Jamaah + Booking/Quotation
              |
              v
Phase 3: Accounting + Quota + Refund
              |
              v
Phase 4: Reporting + Demo + Hardening
              |
              v
Phase 5: Portal Jamaah
```

Fase tidak dijalankan paralel karena model dan kontrak fase sebelumnya menjadi dasar fase berikutnya. Portal sengaja terakhir agar tidak mengganggu validasi core transaction dan security internal.

## 5. Strategi Git dan Database

Sebelum coding Phase 1, folder project perlu diinisialisasi sebagai Git repository setelah mendapat persetujuan pemilik project. Setiap task kecil menghasilkan commit yang fokus agar AI dapat membandingkan, mereview, atau mengembalikan perubahan secara aman.

Gunakan database terpisah:

- Database development untuk eksplorasi UI/manual.
- Database test khusus automated tests.

Automated test tidak boleh bergantung pada data yang dibuat manual di database development.

## 6. Definition of Done Global

Sebuah fase hanya boleh ditandai selesai bila:

- Seluruh scope fase sudah diimplementasikan.
- Test baru dibuktikan gagal sebelum implementasi dan lulus setelahnya.
- Full test suite modul lulus.
- Modul lulus install/upgrade check Odoo 18.
- Hak akses diuji dari server, bukan hanya berdasarkan tombol yang tersembunyi.
- Tidak ada credential atau data identitas asli dalam repository.
- Dokumentasi dan plan sesuai dengan code aktual.
- Hasil dan bukti verifikasi dilaporkan pada checkpoint.

