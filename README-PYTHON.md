# Versi Python (Django)

Versi Python aplikasi tersedia di folder [`django_store`](./django_store). Aplikasi CodeIgniter/PHP sudah dipensiunkan. Aset gambar, CSS, dan JavaScript yang dapat dipakai ulang tetap dipertahankan.

## Fitur

- Katalog dengan filter kategori, pencarian, paginasi, dan detail produk
- Registrasi, login, dan logout
- Pengaturan username, email, dan foto profil
- Keranjang dengan validasi stok
- Checkout dan pembuatan pesanan atomik, termasuk pengurangan stok
- Riwayat pesanan serta unggah bukti pembayaran
- API pesanan dengan kunci API, API dashboard admin, dan endpoint lokasi/ongkir Komerce
- Pencarian tujuan dan pemilihan ongkir Komerce dari halaman checkout
- Panel Django Admin untuk produk, kategori, diskon, pesanan, dan pesan kontak
- Halaman khusus admin untuk konfirmasi pembayaran dengan bukti transfer

## Menjalankan

Python 3.10 atau lebih baru direkomendasikan.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-python.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
cd django_store
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Buka `http://127.0.0.1:8000`. Gunakan akun superuser untuk mengelola produk dan data melalui `http://127.0.0.1:8000/admin/`.

Database lokal menggunakan SQLite secara default. Untuk mengganti lokasinya, set variabel `DJANGO_DATABASE`. Ongkir checkout awal dikonfigurasi lewat `SHIPPING_FEE` (default `0`); endpoint lokasi dan estimasi ongkir memerlukan `COST_API_KEY`, dan API transaksi memerlukan `API_KEY`. Sebelum deployment, set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, dan `DJANGO_ALLOWED_HOSTS`.

Atur nilai rahasia di `.env` atau melalui environment OS. Jangan commit file `.env`. Endpoint tersedia di `/api`, `/api/transaksi`, `/get-location`, dan `/get-cost`; endpoint `/api` memerlukan header `X-API-Key`.

Media yang diunggah disimpan di `django_store/media/`; jangan menghapus media lama sebelum meninjau isinya.

## Catatan migrasi dari CodeIgniter

Versi Django memakai skema dan migrasi database baru. Menjalankan migrasi Django **tidak** mengubah atau menyalin database lama. Backup database lama dan rencanakan impor data secara terpisah sebelum menggunakan aplikasi pada data produksi. Hash password lama juga memerlukan penanganan khusus sebelum akun lama dapat digunakan.

Tes dasar:

```powershell
cd django_store
python manage.py test
```
