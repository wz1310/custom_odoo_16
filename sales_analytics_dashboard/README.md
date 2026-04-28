# Sales Analytics Dashboard

## Overview
Modul analitik penjualan modern untuk Odoo 16 dengan fitur-fitur canggih:
- Dashboard interaktif dengan chart real-time
- KPI Cards dengan animasi
- Segmentasi data multi-dimensi
- Export data lanjutan (Excel)
- Filter dinamis
- Dark/Light mode support
- Mobile responsive

## Features

### 1. Dashboard Utama
- **KPI Cards**: 7 metrik utama penjualan dengan visualisasi ikon modern
- **Revenue Trends**: Grafik tren bulanan dengan animasi
- **Top Customers**: 5 pelanggan teratas berdasarkan revenue
- **Top Products**: 5 produk terlaris
- **Sales Detail**: Tabel detail transaksi lengkap

### 2. Filter & Segmentasi
- Filter rentang tanggal (date range)
- Group by: Customer, Order, Product, Salesperson, Team, Category
- Multi-level grouping (hierarchical)
- Pencarian real-time

### 3. Export & Reporting
- Export ke Excel dengan format profesional
- Multiple sheets (Summary & Detail)
- Format mata uang dan tanggal otomatis

### 4. User Experience
- Dark/Light mode otomatis
- Animasi loading & transisi
- Keyboard shortcuts (Ctrl+F, Ctrl+R, Escape)
- Mobile responsive
- Auto-refresh setiap 5 menit

## Installation

1. Copy folder `sales_analytics_dashboard` ke direktori addons Odoo
2. Update Apps List di Odoo
3. Install modul "Sales Analytics Dashboard"

## Usage

### Akses Dashboard
- Menu: Sales > Analytics Dashboard
- Atau: Sales > Reporting > Analytics Dashboard

### Menggunakan Filter
1. Pilih rentang tanggal (Date Range)
2. Tambahkan group by (opsional)
3. Klik "Apply Filters"

### Export Data
1. Atur filter sesuai kebutuhan
2. Klik tombol "Export Excel"

### Keyboard Shortcuts
- `Ctrl+F` atau `Cmd+F`: Fokus ke filter tanggal
- `Ctrl+R` atau `Cmd+R`: Refresh data
- `Escape`: Tutup dropdown

## Technical Details

### Architecture
- **Framework**: Odoo 16 Web Framework
- **Frontend**: Owl Components (React-style)
- **Styling**: SCSS dengan CSS Variables
- **Backend**: Python (Odoo ORM)



### API Endpoints

#### GET /sales_analytics/data
Mengambil data analitik dengan filter.

**Parameters:**
- `groupby` (array): Field untuk grouping
- `date_from` (string): Tanggal mulai (YYYY-MM-DD)
- `date_to` (string): Tanggal selesai (YYYY-MM-DD)

**Response:** Rendered HTML template

#### POST /sales_analytics/export_excel
Export data ke Excel.

**Parameters:**
- `groupby` (JSON array): Field untuk grouping
- `date_from` (string): Tanggal mulai
- `date_to` (string): Tanggal selesai

**Response:** File Excel download

## KPI Metrics

1. **Total Revenue**: Total pendapatan dari semua penjualan
2. **Total Orders**: Jumlah total order (sale + done)
3. **Total Customers**: Jumlah pelanggan unik
4. **Total Products**: Jumlah produk yang terjual
5. **Total Quantity**: Total kuantitas terjual
6. **Avg Order Value**: Rata-rata nilai per order
7. **Total Margin**: Total keuntungan (margin)

## Browser Support
- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

## License
LGPL-3

## Author
Odoo Advanced Analytics
