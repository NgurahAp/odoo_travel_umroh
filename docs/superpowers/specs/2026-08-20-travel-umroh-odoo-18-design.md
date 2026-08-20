# Desain Modul Travel Umroh untuk Odoo 18

Tanggal: 20 Agustus 2026  
Target: Odoo 18 Community  
Nama teknis modul: `travel_umroh`

## 1. Ringkasan

Modul Travel Umroh menyediakan back-office untuk mengelola paket, jadwal keberangkatan, jamaah, itinerary, quotation, pembayaran, kuota, dokumen, dan status perjalanan. Modul memanfaatkan aplikasi standar Odoo untuk identitas kontak, quotation, sales order, invoice, payment, credit note, attachment, chatter, dan portal.

Prinsip utama desain adalah membuat hanya domain yang belum tersedia di Odoo. Booking tidak menjadi model transaksi baru; model `sale.order` diperluas dan digunakan sebagai Booking sekaligus Quotation. Dengan demikian, modul tidak menduplikasi customer, total transaksi, invoice, payment, atau audit trail yang sudah disediakan Odoo.

## 2. Tujuan

Fase pertama harus memungkinkan tim internal untuk:

1. Mengelola master maskapai, bandara, dan hotel.
2. Membuat template paket dan jadwal keberangkatan yang dapat dijual berulang kali.
3. Menentukan kuota dan harga per jamaah berdasarkan tipe kamar.
4. Mengelola profil legal jamaah tanpa mencampurkannya dengan akun login internal.
5. Membuat satu booking untuk satu pemesan dengan beberapa peserta.
6. Mengubah booking dari quotation menjadi sales order.
7. Menggunakan invoice, DP, payment, pelunasan, credit note, dan refund bawaan Odoo.
8. Mereservasi seat setelah DP terverifikasi dan mencegah overbooking.
9. Memverifikasi dokumen jamaah.
10. Mengelola status keberangkatan sampai selesai.
11. Menyediakan laporan operasional melalui view standar Odoo.

Fase kedua menambahkan portal agar jamaah dapat melihat data miliknya dan mengunggah dokumen tanpa mengakses backend.

## 3. Batasan Scope

Fitur berikut tidak termasuk fase awal:

- Integrasi WhatsApp.
- Payment gateway.
- Sinkronisasi dan rekonsiliasi bank otomatis.
- Waitlist.
- Pengaturan nomor kamar dan roommate.
- Multi-company.
- Custom dashboard berbasis JavaScript/OWL.
- Customer self-registration publik.
- Pengelolaan visa yang lengkap.
- Perpindahan data dari sistem lama.

Implementasi awal menggunakan mata uang perusahaan, yaitu IDR. Konfigurasi pajak, chart of accounts, journal, dan produk akuntansi mengikuti konfigurasi standar database Odoo dan lokalisasi Indonesia yang digunakan pada database.

## 4. Aplikasi Odoo yang Digunakan

Modul bergantung pada kemampuan standar berikut:

- `base`: user, group, company, currency, dan external ID.
- `contacts`: pengelolaan `res.partner`.
- `mail`: chatter, activity, dan audit perubahan.
- `sale_management`: quotation, sales order, order line, dan down payment.
- `account`: customer invoice, payment, credit note, dan refund.
- `portal`: digunakan pada fase portal.

Data dan kode custom disimpan dalam add-on `travel_umroh` pada folder add-ons lokal yang sudah dipasang ke `/mnt/extra-addons` di container Odoo.

## 5. Arsitektur Data

### 5.1 Gambaran Relasi

```text
res.partner
     ▲
     │ partner_id (unik)
travel.jamaah
     ▲
     │ jamaah_id
travel.booking.participant
     │
     │ order_id
     ▼
sale.order ─────────────────────────> account.move
     │                                  invoice/credit note
     │ departure_id
     ▼
travel.departure
├── travel.departure.price[]
├── travel.departure.flight[]
└── travel.departure.accommodation[]
     ▲
     │ package_id
travel.package
```

Model dengan prefix `travel.*` merupakan model custom dan secara normal menghasilkan tabel PostgreSQL dengan titik diganti garis bawah. Model `sale.order`, `res.partner`, `account.move`, dan `res.users` merupakan model standar Odoo yang diperluas atau direferensikan.

### 5.2 `travel.package`

Merepresentasikan template penawaran yang dapat memiliki banyak jadwal keberangkatan.

Field utama:

- `name`: nama paket.
- `code`: kode internal yang unik.
- `product_id`: service product Odoo yang dipakai pada Sales Order dan invoice.
- `duration_days`: lama perjalanan sebagai informasi produk.
- `description`: deskripsi dan fasilitas umum.
- `active`: mendukung archive tanpa menghapus histori.

Package tidak menyimpan tanggal, kuota, harga, flight, atau hotel yang spesifik. Data tersebut berada pada departure.

`product_id` harus menunjuk ke produk bertipe service dengan invoicing policy berdasarkan ordered quantity. Harga pada produk tidak menjadi sumber harga transaksi; `price_unit` tetap diambil dari harga departure agar setiap jadwal dapat mempunyai harga berbeda. Penggunaan product standar memastikan order line dapat mengikuti flow invoice dan down payment bawaan Odoo.

### 5.3 `travel.departure`

Merepresentasikan satu keberangkatan spesifik dari sebuah package.

Field utama:

- `name`: nama tampilan, dapat dibentuk dari package dan tanggal.
- `package_id`: Many-to-one ke `travel.package`.
- `departure_date`: tanggal keberangkatan.
- `return_date`: tanggal kepulangan.
- `quota`: total seat yang dapat dijual.
- `currency_id`: mata uang harga, default mata uang perusahaan.
- `state`: `draft`, `open`, `departed`, `done`, atau `cancelled`.
- `reserved_seats`: computed dari participant yang seat-nya sudah direservasi.
- `remaining_seats`: `quota - reserved_seats`.
- `is_full`: computed ketika sisa seat nol.

Aturan:

- Tanggal pulang harus sesudah tanggal berangkat.
- Kuota tidak boleh negatif.
- Departure hanya dapat dipilih pada quotation ketika berstatus `open` dan belum penuh.
- Departure hanya dapat dibuka bila harga Quad, Triple, dan Double sudah lengkap.
- Status penuh merupakan kondisi computed, bukan state yang diubah manual.
- Departure tidak dapat menjadi `departed` jika masih ada participant dengan dokumen wajib yang belum terverifikasi.

### 5.4 `travel.departure.price`

Menyimpan harga per jamaah untuk setiap tipe kamar.

Field utama:

- `departure_id`.
- `room_type`: enum `quad`, `triple`, atau `double`.
- `price`: nilai Monetary.
- `currency_id`: related dari departure.

Constraint gabungan `departure_id + room_type` harus unik. Harga tidak boleh negatif.

### 5.5 Master Penerbangan

`travel.airline` menyimpan:

- Nama maskapai.
- Kode IATA bila tersedia.
- Status aktif.

`travel.airport` menyimpan:

- Nama bandara.
- Kode IATA.
- Kota.
- Negara menggunakan `res.country`.
- Status aktif.

`travel.departure.flight` menyimpan itinerary penerbangan:

- `departure_id`.
- `sequence`.
- `airline_id`.
- `flight_number`.
- `origin_airport_id` dan `origin_terminal`.
- `destination_airport_id` dan `destination_terminal`.
- `departure_datetime` dan `arrival_datetime`.

Aturan:

- Waktu tiba harus sesudah waktu berangkat.
- Bandara asal dan tujuan tidak boleh sama.
- Urutan itinerary ditampilkan berdasarkan `sequence`.
- Satu departure dapat memiliki penerbangan pergi, transit, lanjutan, dan pulang.

### 5.6 Master Hotel dan Akomodasi

`travel.hotel` menyimpan:

- Nama hotel.
- Kota.
- Rating bintang 1–5.
- Jarak ke masjid sebagai informasi opsional.
- Status aktif.

`travel.departure.accommodation` menyimpan:

- `departure_id`.
- `sequence`.
- `hotel_id`.
- `check_in`.
- `check_out`.

Aturan:

- Check-out harus sesudah check-in.
- Tanggal menginap harus berada dalam rentang departure, kecuali Manager memberikan koreksi yang sah sebelum departure dibuka.
- Satu departure dapat menggunakan beberapa hotel tanpa field khusus Makkah/Madinah.

### 5.7 `res.partner` dan `travel.jamaah`

`res.partner` tetap menjadi sumber data kontak: nama, email, telepon, dan alamat. `travel.jamaah` merupakan profil domain yang terhubung one-to-one melalui `partner_id`.

Field utama `travel.jamaah`:

- `partner_id`: wajib dan unik.
- `nik`: wajib dan unik.
- `birth_place`.
- `birth_date`.
- `age`: computed dari tanggal lahir.
- `gender`.
- `passport_number`: opsional pada pendaftaran awal dan unik bila diisi.
- `passport_expiry`: opsional sampai paspor tersedia.
- `emergency_contact_name`.
- `emergency_contact_phone`.
- `ktp_file` dan nama file.
- `passport_file` dan nama file.
- `document_status`: `incomplete`, `pending`, atau `verified`.
- `verified_by` dan `verified_at`.

File binary harus disimpan sebagai attachment Odoo, bukan sebagai blob inline yang memperbesar row bisnis. Data identitas sensitif hanya dapat dibaca oleh group Travel yang sesuai.

Internal staff tetap menggunakan `res.users` yang terhubung ke `res.partner`; staff tidak memiliki record `travel.jamaah` kecuali orang tersebut juga menjadi peserta perjalanan. Portal jamaah pada fase kedua menggunakan `res.users` tipe Portal yang terhubung ke partner pada profil jamaah yang sama.

### 5.8 Perluasan `sale.order`

Tidak ada model `travel.booking`. `sale.order` menjadi Booking dan Quotation dengan field tambahan:

- `is_travel_booking`: membedakan transaksi travel dari sales order biasa.
- `departure_id`: jadwal yang dipesan.
- `participant_ids`: One-to-many ke `travel.booking.participant`.
- `travel_payment_state`: computed `unpaid`, `dp`, `paid`, atau `refunded`.
- `travel_state`: `registered`, `departed`, atau `done`; pembatalan tetap memakai state Sales Order standar.
- `seat_reserved`: penanda idempotent bahwa participant sudah memakai kuota.
- `seat_reserved_at`.

Field bawaan yang digunakan:

- `partner_id`: pemesan/penanggung jawab pembayaran, yang tidak wajib menjadi participant.
- `user_id`: staff yang bertanggung jawab.
- `state`: status quotation/sales order.
- `order_line`: rincian harga.
- `invoice_ids`: invoice dan credit note.
- `amount_total`: total booking.
- `message_ids`: Chatter.

### 5.9 `travel.booking.participant`

Merepresentasikan peserta dalam sebuah booking.

Field utama:

- `order_id`: Many-to-one ke `sale.order`.
- `jamaah_id`: Many-to-one ke `travel.jamaah`.
- `room_type`: enum Quad/Triple/Double.
- `unit_price`: snapshot harga saat participant ditambahkan.
- `currency_id`: related dari order/departure.
- `sale_line_id`: order line yang mewakili harga participant.

Aturan:

- Kombinasi `order_id + jamaah_id` harus unik.
- Jamaah dapat berbeda dari `sale.order.partner_id`.
- Harga awal diambil dari `travel.departure.price`.
- Harga dapat di-refresh selama quotation masih draft.
- Setelah Sales Order dikonfirmasi, participant dan harga terkunci bagi Staff.
- Hanya Manager yang dapat melakukan override harga atau koreksi participant setelah konfirmasi, dan semua koreksi dicatat di Chatter.

Setiap participant menghasilkan satu `sale.order.line` dengan product dari package, quantity 1, dan `price_unit` sama dengan snapshot participant. Sale line menyimpan relasi balik ke participant agar sinkronisasi dan audit eksplisit.

## 6. Workflow Bisnis

### 6.1 Persiapan Penjualan

1. Manager membuat master airline, airport, dan hotel.
2. Manager membuat package.
3. Manager membuat departure, kuota, tiga harga kamar, flight itinerary, dan accommodation itinerary.
4. Manager mengubah departure dari `draft` menjadi `open`.

### 6.2 Quotation dan Sales Order

1. Staff membuat `sale.order` dengan `is_travel_booking = True`.
2. Staff memilih pemesan dan departure.
3. Staff menambahkan satu atau beberapa jamaah serta tipe kamar masing-masing.
4. Server mengambil harga departure dan membuat snapshot participant serta order line.
5. Quotation dapat disimpan atau dikirim kepada pemesan.
6. Draft/sent quotation belum mengurangi kuota.
7. Setelah pemesan setuju, Staff mengonfirmasi quotation menjadi Sales Order.
8. Konfirmasi mengunci harga dan participant bagi Staff, tetapi belum mereservasi seat.

### 6.3 DP, Reservasi Seat, dan Pelunasan

1. Finance menggunakan down payment bawaan Odoo untuk membuat invoice DP berupa persentase atau nominal tetap.
2. Invoice DP dikonfirmasi/posted.
3. Finance mendaftarkan pembayaran menggunakan mekanisme payment Odoo.
4. Ketika invoice DP sudah tidak memiliki residual yang belum dibayar, modul melakukan reservasi seat secara idempotent.
5. Sebelum reservasi, server menghitung sisa kuota dalam transaksi yang aman terhadap dua reservasi bersamaan.
6. Jika participant melebihi sisa seat, reservasi ditolak dengan pesan yang menjelaskan jumlah seat yang tersedia dan dibutuhkan.
7. Jika berhasil, `seat_reserved` diset dan participant mulai dihitung ke `reserved_seats` departure.
8. Finance membuat invoice pelunasan melalui flow standar Sales.
9. `travel_payment_state` dihitung dari invoice posted, residual, down payment, dan credit note; field tidak dapat diedit manual.
10. Booking menjadi `paid` jika nilai yang harus diinvoicekan telah diinvois dan seluruh residual invoice neto telah lunas.

### 6.4 Dokumen dan Perjalanan

1. Staff mengunggah KTP dan paspor yang tersedia.
2. Paspor boleh kosong pada pendaftaran awal.
3. Staff mengubah status menjadi `pending` setelah dokumen lengkap.
4. Manager memverifikasi dan sistem menyimpan user serta waktu verifikasi.
5. Departure tidak dapat ditandai `departed` bila participant aktif masih memiliki dokumen wajib yang belum verified.
6. Manager mengubah status perjalanan menjadi `departed`, lalu `done` setelah perjalanan selesai.

### 6.5 Pembatalan dan Refund

Sebelum DP:

- Sales Order dibatalkan menggunakan flow standar.
- Tidak ada seat yang dilepas karena belum direservasi.
- Tidak ada refund.

Setelah DP:

1. Hanya Manager yang dapat memulai pembatalan travel.
2. Modul mencatat alasan pembatalan di Chatter.
3. Seat dilepas satu kali secara idempotent.
4. Finance membuat Credit Note/refund menggunakan mekanisme Odoo.
5. `travel_payment_state` memperhitungkan credit note dan menjadi `refunded` ketika transaksi telah dibalik sepenuhnya.

## 7. Hak Akses

### 7.1 Groups

Modul mendefinisikan tiga group internal:

- `travel_umroh.group_travel_staff`.
- `travel_umroh.group_travel_finance`.
- `travel_umroh.group_travel_manager`.

Manager mewarisi kemampuan Staff dan Finance. System Administrator tetap menggunakan group administrasi bawaan Odoo dan tidak diduplikasi menjadi role custom.

### 7.2 Matriks Akses

| Operasi | Staff | Finance | Manager |
|---|---:|---:|---:|
| Melihat seluruh booking travel | Ya | Ya | Ya |
| Membuat/mengubah quotation | Ya | Lihat | Ya |
| Mengelola jamaah sebelum terkunci | Ya | Lihat | Ya |
| Mengelola package/departure/master | Lihat | Lihat | Ya |
| Override harga | Tidak | Tidak | Ya |
| Membuat/post invoice dan payment | Tidak | Ya | Ya |
| Membatalkan setelah DP | Tidak | Memproses refund | Ya |
| Menghapus master yang belum dipakai | Tidak | Tidak | Ya |

Tidak ada Record Rule "hanya booking sendiri" pada fase awal. Seluruh Staff dapat melihat booking travel agar operasional dapat saling menggantikan. Akses sensitif ditegakkan melalui ACL, group field, dan pemeriksaan group pada server method; menyembunyikan tombol tidak dianggap sebagai pengamanan.

### 7.3 Portal Fase Kedua

Portal user hanya dapat mengakses record yang partner pemesan atau profil jamaahnya terhubung dengan user tersebut. Portal dapat:

- Melihat booking, itinerary, quotation, dan invoice miliknya.
- Melihat participant dalam booking yang menjadi tanggung jawabnya.
- Mengunggah KTP/paspor.
- Memperbarui data yang belum verified.

Portal tidak dapat mengakses backend, melihat booking lain, memverifikasi dokumen, mengubah harga, mengubah status pembayaran, atau membatalkan booking langsung.

## 8. Antarmuka

Fase awal memakai XML view standar Odoo dan tidak menambahkan OWL/JavaScript custom.

Menu aplikasi:

```text
Travel Umroh
├── Bookings
├── Jamaah
├── Packages
├── Departures
├── Reporting
└── Configuration
    ├── Airlines
    ├── Airports
    └── Hotels
```

Action Bookings membuka `sale.order` dengan domain `is_travel_booking = True`. Configuration hanya terlihat bagi Manager.

Form Booking menambahkan bagian Departure, Participant, status pembayaran, status perjalanan, smart button invoice, dan Chatter pada form Sales Order. Form Departure memakai tab Pricing, Flights, Accommodations, dan Bookings. Form Jamaah memisahkan identitas, kontak, paspor, kontak darurat, dokumen, dan verifikasi.

## 9. Laporan

Fase awal memakai list, search, pivot, graph, dan report action standar Odoo untuk:

- Booking per departure.
- Kuota total, terpakai, dan tersisa.
- Jamaah berdasarkan status dokumen.
- Booking berdasarkan status pembayaran.
- Total penjualan per package/departure.
- Manifest jamaah per departure.
- Sisa tagihan melalui laporan customer invoice Odoo.

Tidak ada custom dashboard JavaScript. Manifest dapat dibuat sebagai report cetak hanya bila diperlukan untuk deliverable interview setelah flow utama stabil.

## 10. Error Handling dan Audit

Semua constraint penting divalidasi di server agar tidak dapat dilewati melalui RPC/import. Pesan error menggunakan istilah bisnis dan menyebut data yang perlu diperbaiki.

Model penting memakai `mail.thread` atau Chatter yang sudah tersedia pada Sales Order untuk melacak:

- Perubahan status.
- Override harga.
- Koreksi participant.
- Verifikasi dokumen.
- Reservasi dan pelepasan seat.
- Pembatalan.
- Invoice, payment, credit note, dan refund terkait.

Operasi reservasi seat dan pelepasan seat harus idempotent. Mengulang callback atau action yang sama tidak boleh menggandakan atau mengurangi kuota dua kali.

## 11. Testing

### 11.1 Model dan Constraint

- Tanggal departure dan return valid.
- Harga unik per departure dan room type.
- Harga dan kuota non-negatif.
- Flight arrival sesudah departure.
- Accommodation check-out sesudah check-in.
- Partner profil jamaah unik.
- NIK unik.
- Paspor unik jika terisi.
- Participant tidak duplikat dalam satu order.

### 11.2 Workflow

- Draft quotation tidak mengurangi kuota.
- Konfirmasi Sales Order belum mengurangi kuota.
- DP yang belum lunas tidak mengurangi kuota.
- DP terverifikasi mereservasi participant tepat satu kali.
- Overbooking ditolak.
- Harga tidak berubah setelah konfirmasi.
- Pembatalan setelah DP melepas seat tepat satu kali.
- Credit Note memperbarui payment state.
- Departure dengan dokumen tidak lengkap tidak dapat menjadi departed.

### 11.3 Security

- Staff tidak dapat override harga.
- Staff tidak dapat memproses invoice/payment tanpa group yang sesuai.
- Finance dapat memproses invoice/payment tetapi tidak mengubah master travel.
- Manager dapat mengelola master dan pembatalan.
- Pada fase kedua, Portal tidak dapat membaca booking yang tidak terkait dengannya.
- Pada fase kedua, Portal tidak dapat memanggil server action internal melalui RPC.

### 11.4 Integration

- Quotation travel dapat dikonfirmasi menjadi Sales Order.
- Participant menghasilkan order line yang benar.
- Down payment invoice terhubung ke Sales Order.
- Pembayaran mengubah status dan reservasi.
- Pelunasan menghasilkan status paid.
- Credit Note/refund terhubung dan tercermin pada status travel.

## 12. Demo Data

Demo data untuk presentasi interview mencakup:

- Tiga airline dan beberapa airport.
- Hotel di Makkah dan Madinah.
- Satu package dengan dua departure.
- Service product yang terhubung ke package.
- Harga Quad/Triple/Double.
- Flight dan accommodation itinerary.
- Beberapa profil jamaah.
- Quotation Draft, booking dengan DP, dan booking Lunas.

Demo data hanya dimuat ketika database mengaktifkan demo data dan tidak menjadi master data production.

## 13. Acceptance Criteria Fase Internal

Fase internal selesai jika:

1. Modul dapat di-install dan di-upgrade pada Odoo 18 tanpa error.
2. Manager dapat menyiapkan package dan departure lengkap.
3. Staff dapat membuat quotation multi-participant dengan harga otomatis.
4. Harga tersimpan sebagai snapshot dan terlindungi dari perubahan tidak sah.
5. Quotation dapat mengikuti flow Sales, down payment, invoice, dan payment standar.
6. DP yang terverifikasi mereservasi seat dan overbooking ditolak.
7. Dokumen dapat diunggah serta diverifikasi.
8. Pembatalan dan credit note melepaskan seat serta menjaga audit trail.
9. Matriks hak akses lolos automated tests.
10. Laporan operasional dasar dapat ditampilkan tanpa custom dashboard.
11. Demo flow dapat dijalankan dari awal sampai selesai pada database development.

## 14. Strategi Fase

Fase 1 membangun back-office internal, accounting integration, laporan standar, demo data, dan test. Fase 2 baru menambahkan controller, template portal, upload dokumen oleh jamaah, record rules portal, dan portal integration tests.

Pemisahan ini menjaga implementasi pertama fokus pada core transaction dan security. Portal tidak mengubah model inti; ia menjadi interface tambahan di atas partner, jamaah, Sales Order, invoice, dan itinerary yang sama.
