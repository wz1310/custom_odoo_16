# Stock Lot Report

## Deskripsi
Addon ini menyediakan laporan stok on-hand berdasarkan Lot/Serial Number untuk produk yang ada di lokasi internal/transit.

## Fitur
- **Laporan Stok per Lot**: Menampilkan detail stok dengan kolom:
  - Lokasi
  - Produk
  - Lot/Serial Number
  - UoM (Unit of Measure)
  - On Hand Qty

- **Filter Tanggal**: Cek stok per tanggal tertentu (menghitung qty berdasarkan stock.move.line yang sudah done sampai tanggal tersebut)

- **KPI Cards**: Menampilkan ringkasan:
  - Total Lokasi
  - Total Produk
  - Total Lot/Serial
  - Total On Hand Qty

- **Export Excel**: Download laporan dalam format XLSX

## Instalasi
1. Copy folder `stock_lot_report` ke direktori addons Odoo
2. Update Apps List
3. Install addon "Stock Lot Report"

## Penggunaan
1. Buka menu: **Inventory > Stock Lot Report**
2. Gunakan filter tanggal untuk cek stok per tanggal tertentu (opsional)
3. Klik **Filter** untuk refresh data
4. Klik **Export Excel** untuk download laporan

## Catatan Teknis
- Addon ini menggunakan `stock.quant` untuk data stok saat ini
- Jika filter tanggal diisi, sistem akan menghitung qty berdasarkan `stock.move.line` yang sudah done
- Hanya menampilkan stok di lokasi dengan usage 'internal' atau 'transit'
- Produk tanpa lot akan ditampilkan dengan label "Tidak ada lot"

## Dependencies
- stock
- web

## Versi
16.0.1.0.0

## License
LGPL-3
