import sqlite3

# Fungsi untuk mendapatkan koneksi database SQLite
def get_db_connection():
    conn = sqlite3.connect(r'C:\Users\PC\Documents\Dinar\Skripsi\[7] ALIZA - spp default prediction\code-master\siswa_db.sqlite')
    conn.row_factory = sqlite3.Row  # Membaca hasil query sebagai dictionary
    return conn

# Membuat database dan tabel siswa
def create_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Membuat tabel siswa jika belum ada
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS siswa (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nipd TEXT NOT NULL UNIQUE,
        nama TEXT,
        penghasilan_ayah TEXT,
        pekerjaan_ibu TEXT,
        pendidikan_ibu TEXT,
        penghasilan_ibu TEXT,
        kelas TEXT,
        spp_normal INTEGER, 
        potongan_spp TEXT,
        harus_dibayar INTEGER 
    )
    ''')

    # Menyimpan perubahan dan menutup koneksi
    conn.commit()
    conn.close()

# Memanggil fungsi untuk membuat database dan tabel
create_db()

print("Database dan tabel 'siswa' berhasil dibuat!")
