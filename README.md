# Travel Umroh untuk Odoo 18

Modul back-office Travel Umroh berbasis Odoo 18 Community dan PostgreSQL 15. Modul ini memakai Sales Order sebagai Booking, Accounting standar sebagai sumber kebenaran invoice/pembayaran/refund, serta model Travel untuk paket, keberangkatan, Jamaah, kapasitas, dokumen, dan laporan operasional.

## Prasyarat

- Docker Desktop dengan Docker Compose
- Git

## Menjalankan layanan

```bash
docker compose up -d
docker compose ps
```

Buka [http://localhost:8069](http://localhost:8069).

Selalu pisahkan database development, test, acceptance, dan demo. Jangan pernah menghapus database atau Docker volume tanpa persetujuan pemilik data.

## Install dan upgrade tanpa demo

Gunakan nama database yang dipastikan belum pernah dipakai. Contoh berikut memakai `travel_umroh_local_fresh`:

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_local_fresh \
  -i base,travel_umroh --without-demo=all

docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_local_fresh \
  -u travel_umroh --without-demo=all
```

## Automated test

Full standard suite:

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test -u travel_umroh --without-demo=all \
  --test-enable --test-tags /travel_umroh --log-level=test
```

Tes konkurensi PostgreSQL dijalankan terpisah karena memakai tag `database_breaking`:

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_phase4_test -u travel_umroh --without-demo=all \
  --test-enable --test-tags database_breaking --log-level=test
```

## Peran internal

- **Staff:** mengelola Booking/Jamaah sesuai workflow, membaca master dan laporan; tidak boleh membuat invoice, pembayaran, atau refund.
- **Finance:** membaca transaksi Travel dan mengelola invoice, pembayaran, serta refund; tidak boleh mengubah Booking.
- **Manager:** mengelola master/keberangkatan, verifikasi dokumen, Booking terbatas dan diaudit, Accounting, serta seluruh laporan.
- **System Administrator:** mempertahankan akses pengelolaan internal dengan workflow dan audit bisnis tetap berlaku.

## Database demo terkendali

Demo hanya dimuat ketika instalasi tidak memakai `--without-demo=all`. Gunakan database khusus yang belum pernah dipakai:

```bash
docker compose run --rm odoo --stop-after-init \
  -d travel_umroh_demo_local \
  -i base,travel_umroh
```

Hasil yang diharapkan adalah tepat tiga Booking sintetis: `DEMO-DRAFT` berstatus Draft/Belum Bayar, `DEMO-DP` berstatus Sales Order/DP, dan `DEMO-PAID` berstatus Sales Order/Lunas dengan dua kursi terpakai. Semua alamat email demo memakai domain `.example.test` dan tidak mengirim email nyata tanpa konfigurasi SMTP.

## Dokumentasi

- [Product requirement](Requirement_Modul_Travel_Umroh.md)
- [Technical design](docs/superpowers/specs/2026-08-20-travel-umroh-odoo-18-design.md)
- [Roadmap](docs/superpowers/plans/2026-08-20-travel-umroh-roadmap.md)
- [Plan Phase 1](docs/superpowers/plans/2026-08-20-phase-1-foundation-master-data.md)
- [Plan Phase 2](docs/superpowers/plans/2026-08-21-phase-2-jamaah-booking-quotation.md)
- [Plan Phase 3](docs/superpowers/plans/2026-08-22-phase-3-accounting-quota-cancellation-refund.md)
- [Plan Phase 4](docs/superpowers/plans/2026-08-22-phase-4-reporting-demo-hardening.md)
- [Panduan demo Phase 4](docs/phase4-demo-flow.md)
- [Panduan end-to-end dari database kosong](docs/travel-umroh-end-to-end-guide.md)

## Batas scope

Phase 5 Portal masih ditunda. Modul ini belum mengimplementasikan portal/self-service, WhatsApp, payment gateway, bank synchronization, waitlist, alokasi kamar/roommate, visa API, airline manifest API, aplikasi mobile, migrasi legacy, konsolidasi multi-company, atau reporting multi-currency.
