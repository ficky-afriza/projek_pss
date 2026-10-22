# Toko Online Django

Aplikasi toko online ini sekarang menggunakan Python dan Django. Source CodeIgniter/PHP telah dipensiunkan; backend aktif berada di [`django_store`](./django_store).

## Fitur

- Katalog dengan filter kategori, pencarian, paginasi, dan detail produk
- Registrasi, autentikasi, profil, dan foto profil
- Keranjang dengan validasi stok
- Checkout transaksional, diskon harian, dan riwayat pesanan
- Unggah bukti pembayaran dan pengelolaan melalui Django Admin
- Halaman admin khusus untuk meninjau bukti dan mengonfirmasi/menolak pesanan
- API transaksi dan integrasi endpoint lokasi/ongkir Komerce
- Pencarian lokasi dan pilihan tarif pengiriman langsung di checkout

## Menjalankan secara lokal

Persyaratan: Python 3.10 atau lebih baru.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-python.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Set-Location django_store
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Buka `http://127.0.0.1:8000`. Panel admin tersedia di `/admin/`.

Atur `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `API_KEY`, `COST_API_KEY`, dan `SHIPPING_FEE` di `.env`. Jangan menimpa `.env` yang sudah berisi konfigurasi pribadi atau meng-commit file tersebut. SQLite digunakan secara default.

## Pengujian

```powershell
Set-Location django_store
python manage.py check
python manage.py test
```

Dokumentasi API dan cara mengimpor koleksi Postman: [`docs/API.md`](docs/API.md). File koleksinya ada di [`docs/postman/TokoFR.postman_collection.json`](docs/postman/TokoFR.postman_collection.json). Dokumentasi deployment: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). Skema data Django: [`docs/SCHEMA.md`](docs/SCHEMA.md).

## Data aplikasi lama

Database dan file media lama tidak dihapus, tetapi belum diimpor ke skema Django. Buat backup dan rencanakan proses migrasi data sebelum menggunakan aplikasi baru pada data produksi. Hash password CodeIgniter juga tidak dapat digunakan langsung sebagai hash password Django.
