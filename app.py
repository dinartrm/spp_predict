from flask import Flask, render_template, request, redirect, url_for, make_response
import joblib
import numpy as np
import os
import sqlite3

# Inisialisasi Flask app
app = Flask(__name__)

# =======================
# === CONFIGURATIONS ===
# =======================
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'decision_tree_model.pkl')
DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'siswa_db.sqlite')

# Load trained model
model = joblib.load(MODEL_PATH)

# =========================
# === UTILITY FUNCTIONS ===
# =========================

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def income_range_to_numeric(income_range):
    if income_range == 'Tidak Berpenghasilan':
        return 0
    try:
        ranges = income_range.replace('Rp. ', '').replace('.', '').replace(',', '').split(' - ')
        if len(ranges) == 2:
            min_val = int(ranges[0].strip())
            max_val = int(ranges[1].strip())
            return (min_val + max_val) / 2
    except:
        return 0
    return 0

def calculate_spp_normal(kelas):
    return 600000 if kelas == '10' else 550000 if kelas in ['11', '12'] else 0

def calculate_harus_dibayar(spp_normal, potongan_spp):
    if potongan_spp == 'Potongan 30%':
        return spp_normal * 0.7
    elif potongan_spp == 'Potongan 50%':
        return spp_normal * 0.5
    elif potongan_spp == 'Potongan 70%':
        return spp_normal * 0.3
    return spp_normal

# ========================
# === ROUTE: DASHBOARD ===
# ========================
@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()

    total_siswa = cursor.execute("SELECT COUNT(*) FROM siswa").fetchone()[0]
    bantuan_30 = cursor.execute("SELECT COUNT(*) FROM siswa WHERE potongan_spp = '30%'").fetchone()[0]
    bantuan_50 = cursor.execute("SELECT COUNT(*) FROM siswa WHERE potongan_spp = '50%'").fetchone()[0]
    bantuan_70 = cursor.execute("SELECT COUNT(*) FROM siswa WHERE potongan_spp = '70%'").fetchone()[0]
    tidak_menerima = cursor.execute("SELECT COUNT(*) FROM siswa WHERE potongan_spp = 'Tidak Layak'").fetchone()[0]


    bantuan = cursor.execute('''
        SELECT AVG((penghasilan_ayah + penghasilan_ibu) / 2.0)
        FROM siswa
        WHERE potongan_spp IN ('30%', '50%', '70%')
    ''').fetchone()[0]

    conn.close()

    return render_template('index.html',
                           total_siswa=total_siswa,
                           bantuan_30=bantuan_30,
                           bantuan_50=bantuan_50,
                           bantuan_70=bantuan_70,
                           tidak_menerima=tidak_menerima,
                           rata_rata_penghasilan=bantuan or 0,
                           title="Beranda")

@app.route('/cek')
def cek_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    data = cursor.execute("SELECT * FROM siswa").fetchall()
    conn.close()
    return '<br>'.join([str(dict(row)) for row in data])


# ==========================
# === ROUTE: INPUT FORM ===
# ==========================
@app.route('/input', methods=['GET', 'POST'])
def input_data():
    if request.method == 'POST':
        # Ambil data dari form
        nipd = request.form['nipd']
        nama = request.form['nama']
        penghasilan_ayah = request.form['penghasilan_ayah']
        penghasilan_ibu = request.form['penghasilan_ibu']
        pekerjaan_ibu = request.form['pekerjaan_ibu']
        pendidikan_ibu = request.form['pendidikan_ibu']
        kelas = request.form['kelas']

        # Persiapan data untuk prediksi
        penghasilan_ayah_numeric = income_range_to_numeric(penghasilan_ayah)
        penghasilan_ibu_numeric = income_range_to_numeric(penghasilan_ibu)

        # Mapping teks pekerjaan ke index
        pekerjaan_mapping = {
            'Tidak Bekerja': 0,
            'Karyawan Swasta': 1,
            'Wiraswasta': 2,
            'PNS/TNI/Polri': 3,
            'Petani': 4,
            'Pedagang Kecil': 5,
            'TKI': 6,
            'Buruh': 7,
            'Wirausaha': 8,
            'Lainnya': 9
        }
        pekerjaan_index = pekerjaan_mapping.get(pekerjaan_ibu, 0)
        pekerjaan_ibu_encoded = [0] * 10
        if 0 <= pekerjaan_index < len(pekerjaan_ibu_encoded):
            pekerjaan_ibu_encoded[pekerjaan_index] = 1

        # Encoding pendidikan ibu
        pendidikan_ibu_mapping = {
            'Tidak diketahui': 0, 'SD / sederajat': 1, 'SMP / sederajat': 2,
            'SMA / sederajat': 3, 'D1': 4, 'D2': 5, 'D3': 6, 'D4': 7, 'S1': 8, 'S2': 9
        }
        pendidikan_ibu_encoded = pendidikan_ibu_mapping.get(pendidikan_ibu, -1)

        # Gabung semua fitur untuk prediksi
        input_features = np.array([[penghasilan_ayah_numeric, penghasilan_ibu_numeric] + pekerjaan_ibu_encoded + [pendidikan_ibu_encoded]])
        prediction = model.predict(input_features)[0]
        spp_normal = calculate_spp_normal(kelas)
        harus_dibayar = calculate_harus_dibayar(spp_normal, prediction)

        return render_template('input.html',
                               prediction=prediction,
                               spp_normal=spp_normal,
                               harus_dibayar=harus_dibayar,
                               nipd=nipd,
                               nama=nama,
                               penghasilan_ayah=penghasilan_ayah,
                               penghasilan_ibu=penghasilan_ibu,
                               pekerjaan_ibu=pekerjaan_ibu,
                               pendidikan_ibu=pendidikan_ibu,
                               kelas=kelas,
                               title="Input Data Siswa")
    
    # Untuk GET: kosongkan form + cegah cache
    response = make_response(render_template('input.html', title="Input Data Siswa"))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# ====================
# === ROUTE: SAVE ===
# ====================
@app.route('/save', methods=['POST'])
def save_data():
    nipd = request.form['nipd']
    nama = request.form['nama']
    penghasilan_ayah_raw = request.form['penghasilan_ayah']
    penghasilan_ibu_raw = request.form['penghasilan_ibu']
    pekerjaan_ibu = request.form['pekerjaan_ibu']
    pendidikan_ibu = request.form['pendidikan_ibu']
    kelas = request.form['kelas']
    potongan_spp_raw = request.form.get('potongan_spp')  # bisa "Potongan 70%", dll
    spp_normal = request.form.get('spp_normal')
    harus_dibayar = request.form.get('harus_dibayar')

    # Konversi penghasilan ke angka
    penghasilan_ayah = income_range_to_numeric(penghasilan_ayah_raw)
    penghasilan_ibu = income_range_to_numeric(penghasilan_ibu_raw)

    # Bersihkan potongan_spp jadi cuma "70%", "50%", dst
    potongan_spp = potongan_spp_raw.replace("Potongan ", "") if potongan_spp_raw else "0%"

    conn = get_db_connection()
    cursor = conn.cursor()

    # Cek apakah NIPD sudah terdaftar
    existing = cursor.execute('SELECT * FROM siswa WHERE nipd = ?', (nipd,)).fetchone()
    if existing:
        conn.close()
        return render_template('input.html',
                               message_error="NIPD sudah terdaftar!",
                               nipd=nipd,
                               nama=nama,
                               penghasilan_ayah=penghasilan_ayah_raw,
                               penghasilan_ibu=penghasilan_ibu_raw,
                               pekerjaan_ibu=pekerjaan_ibu,
                               pendidikan_ibu=pendidikan_ibu,
                               kelas=kelas,
                               prediction=potongan_spp,
                               spp_normal=spp_normal,
                               harus_dibayar=harus_dibayar)

    # Simpan ke database
    cursor.execute('''
        INSERT INTO siswa (nipd, nama, penghasilan_ayah, penghasilan_ibu, pekerjaan_ibu, pendidikan_ibu, kelas,
                           potongan_spp, spp_normal, harus_dibayar)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        nipd, nama, penghasilan_ayah, penghasilan_ibu, pekerjaan_ibu,
        pendidikan_ibu, kelas, potongan_spp, spp_normal, harus_dibayar
    ))
    conn.commit()
    conn.close()

    return render_template('input.html', message="Data berhasil disimpan.")

# ==========================
# === ROUTE: DAFTAR DATA ===
# ==========================
@app.route('/daftar')
def daftar_siswa():
    q = request.args.get('q')  # Ambil kata kunci pencarian dari query string
    conn = get_db_connection()

    if q:
        siswa = conn.execute('''
            SELECT * FROM siswa
            WHERE nipd LIKE ? OR nama LIKE ?
        ''', (f'%{q}%', f'%{q}%')).fetchall()
    else:
        siswa = conn.execute('SELECT * FROM siswa').fetchall()

    conn.close()
    return render_template('daftar.html', siswa=siswa, q=q)

# ==========================
# === ROUTE: HAPUS EDIT SEARCH DATA ===
# ==========================
def get_all_siswa():
    conn = get_db_connection()
    siswa_list = conn.execute('SELECT * FROM siswa').fetchall()
    conn.close()
    return siswa_list

@app.route('/hapus/<int:id>', methods=['POST'])
def hapus_siswa(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM siswa WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('daftar_siswa'))

# Route untuk menampilkan form edit
@app.route('/edit/<int:id>')
def edit_siswa(id):
    conn = get_db_connection()
    siswa = conn.execute('SELECT * FROM siswa WHERE id = ?', (id,)).fetchone()
    conn.close()

    # Dropdown options
    penghasilan_opsi = [
        "Kurang dari Rp. 500,000",
        "Rp. 500,000 - Rp. 999,999",
        "Rp. 1,000,000 - Rp. 1,999,999",
        "Rp. 2,000,000 - Rp. 4,999,999",
        "Rp. 5,000,000 - Rp. 20,000,000",
        "Lebih dari Rp. 20,000,000",
        "Tidak Berpenghasilan"
    ]

    pendidikan_opsi = [
        "Tidak diketahui", "SD / sederajat", "SMP / sederajat", "SMA / sederajat",
        "D1", "D2", "D3", "D4", "S1", "S2"
    ]

    return render_template(
        'edit.html',
        siswa=siswa,
        penghasilan_opsi=penghasilan_opsi,
        pendidikan_opsi=pendidikan_opsi
    )

# Route untuk update data dan prediksi ulang
@app.route('/update/<int:id>', methods=['POST'])
def update_siswa(id):
    nipd = request.form['nipd']
    nama = request.form['nama']
    penghasilan_ayah = request.form['penghasilan_ayah']
    penghasilan_ibu = request.form['penghasilan_ibu']
    pekerjaan_ibu = request.form['pekerjaan_ibu']
    pendidikan_ibu = request.form['pendidikan_ibu']
    kelas = request.form['kelas']

    # Konversi income ke angka
    penghasilan_ayah_numeric = income_range_to_numeric(penghasilan_ayah)
    penghasilan_ibu_numeric = income_range_to_numeric(penghasilan_ibu)

    # One-hot encoding pekerjaan ibu
    pekerjaan_ibu_encoded = [0] * 10
    pekerjaan_index = int(pekerjaan_ibu)
    if 0 <= pekerjaan_index < len(pekerjaan_ibu_encoded):
        pekerjaan_ibu_encoded[pekerjaan_index] = 1

    # Encoding pendidikan ibu
    pendidikan_ibu_mapping = {
        'Tidak diketahui': 0, 'SD / sederajat': 1, 'SMP / sederajat': 2,
        'SMA / sederajat': 3, 'D1': 4, 'D2': 5, 'D3': 6, 'D4': 7, 'S1': 8, 'S2': 9
    }
    pendidikan_ibu_encoded = pendidikan_ibu_mapping.get(pendidikan_ibu, -1)

    # Gabung fitur
    input_features = np.array([[penghasilan_ayah_numeric, penghasilan_ibu_numeric] + pekerjaan_ibu_encoded + [pendidikan_ibu_encoded]])

    # Prediksi ulang
    prediction = model.predict(input_features)[0]
    spp_normal = calculate_spp_normal(kelas)
    harus_dibayar = calculate_harus_dibayar(spp_normal, prediction)

    # Simpan ke database
    conn = get_db_connection()
    conn.execute('''
        UPDATE siswa 
        SET nipd = ?, nama = ?, penghasilan_ayah = ?, penghasilan_ibu = ?, 
            pekerjaan_ibu = ?, pendidikan_ibu = ?, kelas = ?, 
            spp_normal = ?, potongan_spp = ?, harus_dibayar = ? 
        WHERE id = ?
    ''', (nipd, nama, penghasilan_ayah, penghasilan_ibu, pekerjaan_ibu, pendidikan_ibu, kelas,
          spp_normal, prediction, harus_dibayar, id))
    conn.commit()
    conn.close()

    return redirect('/daftar')

# ====================
# === MAIN DRIVER ===
# ====================
if __name__ == '__main__':
    app.run(debug=True)
