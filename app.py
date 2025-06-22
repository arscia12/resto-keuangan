from flask import Flask, render_template, request, redirect, send_file
from datetime import datetime
import csv
import os
from collections import defaultdict
import openpyxl
from openpyxl.utils import get_column_letter

app = Flask(__name__)
FILE_CSV = 'keuangan.csv'
MATA_UANG = ['USD', 'IDR', 'KHR']

def buat_file():
    if not os.path.exists(FILE_CSV):
        with open(FILE_CSV, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Tanggal', 'Tipe', 'Deskripsi', 'Mata Uang', 'Jumlah'])

def simpan_transaksi(tipe, deskripsi, mata_uang, jumlah):
    tanggal = datetime.now().strftime('%Y-%m-%d')
    with open(FILE_CSV, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([tanggal, tipe, deskripsi, mata_uang, jumlah])

def ringkasan_hari_ini():
    tanggal = datetime.now().strftime('%Y-%m-%d')
    pemasukan = defaultdict(float)
    pengeluaran = defaultdict(float)

    if not os.path.exists(FILE_CSV):
        return {}, {}, {}

    with open(FILE_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Tanggal'] == tanggal:
                jumlah = float(row['Jumlah'])
                if row['Tipe'].lower() == 'pemasukan':
                    pemasukan[row['Mata Uang']] += jumlah
                else:
                    pengeluaran[row['Mata Uang']] += jumlah

    omset = {mata: pemasukan[mata] - pengeluaran[mata] for mata in MATA_UANG}
    return pemasukan, pengeluaran, omset

def saldo_per_mata_uang():
    saldo = defaultdict(float)

    if not os.path.exists(FILE_CSV):
        return {'USD': 0, 'IDR': 0, 'KHR': 0}

    with open(FILE_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            jumlah = float(row['Jumlah'])
            if row['Tipe'].lower() == 'pemasukan':
                saldo[row['Mata Uang']] += jumlah
            elif row['Tipe'].lower() == 'pengeluaran':
                saldo[row['Mata Uang']] -= jumlah

    return saldo

def saldo_utama():
    kurs = {'USD': 15500, 'KHR': 3.8, 'IDR': 1}
    saldo = saldo_per_mata_uang()
    total_idr = sum(saldo[m] * kurs[m] for m in MATA_UANG)
    return total_idr

def get_transaksi_hari_ini():
    tanggal = datetime.now().strftime('%Y-%m-%d')
    rows = []
    if os.path.exists(FILE_CSV):
        with open(FILE_CSV, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['Tanggal'] == tanggal:
                    rows.append(row)
    return rows

@app.route('/', methods=['GET', 'POST'])
def index():
    buat_file()
    if request.method == 'POST':
        tipe = request.form['tipe']
        deskripsi = request.form['deskripsi']
        mata_uang = request.form['mata_uang']
        jumlah = request.form['jumlah'].replace(',', '.')
        try:
            jumlah = float(jumlah)
            simpan_transaksi(tipe, deskripsi, mata_uang, jumlah)
        except:
            pass
        return redirect('/')

    pemasukan, pengeluaran, omset = ringkasan_hari_ini()
    saldo = saldo_utama()
    return render_template('index.html',
                           pemasukan=pemasukan,
                           pengeluaran=pengeluaran,
                           omset=omset,
                           saldo=saldo,
                           saldo_per_mata_uang=saldo_per_mata_uang(),
                           mata_uang=MATA_UANG)

@app.route('/riwayat')
def riwayat():
    data = get_transaksi_hari_ini()
    return render_template('riwayat.html', data=data)

@app.route('/download')
def download_excel():
    rows = get_transaksi_hari_ini()
    if not rows:
        return "Tidak ada data hari ini.", 404

    nama_file = "riwayat_hari_ini.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Riwayat Hari Ini"

    headers = ['Tanggal', 'Tipe', 'Deskripsi', 'Mata Uang', 'Jumlah']
    ws.append(headers)
    for row in rows:
        ws.append([row[h] for h in headers])

    for col in ws.columns:
        max_len = max(len(str(cell.value)) if cell.value else 0 for cell in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = max_len + 2

    wb.save(nama_file)
    return send_file(nama_file, as_attachment=True)

@app.route('/history')
def history():
    rows = []
    summary = defaultdict(lambda: {
        'USD_in': 0, 'USD_out': 0,
        'IDR_in': 0, 'IDR_out': 0,
        'KHR_in': 0, 'KHR_out': 0
    })
    kurs = {'USD': 15500, 'KHR': 3.8, 'IDR': 1}

    if os.path.exists(FILE_CSV):
        with open(FILE_CSV, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
                tanggal = row['Tanggal']
                jumlah = float(row['Jumlah'])
                mata_uang = row['Mata Uang']
                tipe = row['Tipe'].lower()

                if tipe == 'pemasukan':
                    summary[tanggal][f"{mata_uang}_in"] += jumlah
                elif tipe == 'pengeluaran':
                    summary[tanggal][f"{mata_uang}_out"] += jumlah

    # Hitung omset total IDR per hari
    rekap = []
    for tanggal in sorted(summary):
        s = summary[tanggal]
        omset_idr = (
            (s['USD_in'] - s['USD_out']) * kurs['USD'] +
            (s['IDR_in'] - s['IDR_out']) * kurs['IDR'] +
            (s['KHR_in'] - s['KHR_out']) * kurs['KHR']
        )
        s['tanggal'] = tanggal
        s['omset_idr'] = omset_idr
        rekap.append(s)

    return render_template('history.html', data=rows, rekap=rekap)

if __name__ == '__main__':
    app.run(debug=True)
