from werkzeug.utils import secure_filename
import matplotlib
matplotlib.use('Agg') # <-- BARIS INI DITAMBAHKAN UNTUK MEMPERBAIHKI ERROR
from flask import Flask, render_template, request, redirect, url_for, flash
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import os
import math
import io
import base64
import matplotlib.pyplot as plt

app = Flask(__name__)
# Menambahkan secret key untuk flash messages
app.config['SECRET_KEY'] = 'supersecretkey'

# Membuat direktori 'data' jika belum ada
if not os.path.exists('data'):
    os.makedirs('data')

# Path ke file CSV
DATA_FILE = 'data/sembako.csv'

# Fungsi untuk memuat dan mengklasifikasi data
def klasifikasi_data():
  try:
    df = pd.read_csv(DATA_FILE)
    df.dropna(subset=['id'], inplace=True)
    df['id'] = df['id'].astype(int)
    # Penanganan 'luas_rumah' yang lebih aman
    if 'luas_rumah' in df.columns:
        df['luas_rumah'] = pd.to_numeric(df['luas_rumah'].astype(str).str.replace(' m²', '', regex=False), errors='coerce')
        df['luas_rumah'].fillna(df['luas_rumah'].mean(), inplace=True)
    else:
        # Jika kolom tidak ada, buat dengan nilai default atau NaN
        df['luas_rumah'] = 0.0 # atau pd.NA
        
    # Memilih fitur numerik yang akan digunakan untuk K-Means
    df_numeric = df[['pendapatan', 'jumlah_anggota_keluarga', 'luas_rumah', 'jumlah_kendaraan']]
    
    # Normalisasi data
    scaler = StandardScaler()
    df_scaled = scaler.fit_transform(df_numeric)
    
    # Menjalankan K-Means dengan 3 cluster
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    df['klaster'] = kmeans.fit_predict(df_scaled)
    
    # Menetapkan label kategori berdasarkan hasil K-Means
    # Perhatian: Pemetaan 0, 1, 2 ke 'Layak', 'Tidak Layak', 'Sangat Layak'
    # bersifat sementara dan mungkin perlu disesuaikan setelah menganalisis 
    # karakteristik masing-masing cluster hasil K-Means.
    df['kategori'] = df['klaster'].map({0: 'Layak', 1: 'Tidak Layak', 2: 'Sangat Layak'})
    
    # Dihapus: Logika hard-coded berdasarkan pendapatan yang menimpa hasil K-Means
    
    return df
  except FileNotFoundError:
    return None
  except Exception as e:
    # Menangkap error lain seperti masalah format data
    print(f"Error saat klasifikasi data: {e}")
    return None

# Fungsi untuk memuat data mentah (tanpa klasifikasi)
def load_data_raw():
    try:
        df = pd.read_csv(DATA_FILE)
        return df
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error saat memuat data mentah: {e}")
        return None

# Rute utama (Dashboard) - Tidak ada perubahan signifikan di sini
@app.route('/', methods=['GET', 'POST'])
def index():
    page = request.args.get('page', 1, type=int)
    active_tab = request.args.get('tab', 'sangat-layak')
    per_page = 20
    data_loaded = False
    chart_image = None
    error = None

    if request.method == 'POST' or 'page' in request.args or 'tab' in request.args:
        df = klasifikasi_data()
        if df is not None:
            data_loaded = True
            total_penerima = len(df)
            hasil_klaster = df['kategori'].value_counts().to_dict()

            # --- MEMBUAT GRAFIK SEBAGAI GAMBAR ---
            if hasil_klaster:
                plt.style.use('seaborn-v0_8-deep')
                
                labels = hasil_klaster.keys()
                values = hasil_klaster.values()
                
                fig, ax = plt.subplots(figsize=(10, 6), subplot_kw=dict(aspect="equal"))
                
                explode = tuple([0.05] * len(labels))

                wedges, texts, autotexts = ax.pie(values, autopct='%1.1f%%',
                                                  startangle=140,
                                                  explode=explode,
                                                  shadow=True,
                                                  textprops=dict(color="w", weight="bold"))

                ax.legend(wedges, labels,
                          title="Kategori",
                          loc="center left",
                          bbox_to_anchor=(1, 0, 0.5, 1))

                plt.setp(autotexts, size=12, weight="bold")
                ax.set_title("Distribusi Kategori Penerima Sembako", fontsize=16, weight="bold")

                img = io.BytesIO()
                plt.savefig(img, format='png', bbox_inches='tight', transparent=True)
                img.seek(0)
                
                chart_image = base64.b64encode(img.getvalue()).decode('utf8')
                plt.close(fig)
            # ------------------------------------

            df_sangat_layak = df[df['kategori'] == 'Sangat Layak']
            df_layak = df[df['kategori'] == 'Layak']
            df_tidak_layak = df[df['kategori'] == 'Tidak Layak']

            # Logika pagination untuk setiap tab
            if active_tab == 'sangat-layak':
                current_df = df_sangat_layak
            elif active_tab == 'layak':
                current_df = df_layak
            else:
                current_df = df_tidak_layak
            
            start = (page - 1) * per_page
            end = start + per_page
            
            sangat_layak_page = df_sangat_layak.iloc[start:end].to_dict('records')
            layak_page = df_layak.iloc[start:end].to_dict('records')
            tidak_layak_page = df_tidak_layak.iloc[start:end].to_dict('records')

            # Pastikan id integer untuk tampilan
            for row in sangat_layak_page + layak_page + tidak_layak_page:
                if 'id' in row and row['id'] is not None:
                    try:
                        row['id'] = int(row['id'])
                    except Exception:
                        pass

            # Perhitungan total halaman harus berdasarkan data yang ditampilkan
            if active_tab == 'sangat-layak':
                total_pages = math.ceil(len(df_sangat_layak) / per_page)
            elif active_tab == 'layak':
                total_pages = math.ceil(len(df_layak) / per_page)
            else:
                total_pages = math.ceil(len(df_tidak_layak) / per_page)

            return render_template('index.html',
                                   total_penerima=total_penerima,
                                   hasil_klaster=hasil_klaster,
                                   sangat_layak=sangat_layak_page,
                                   layak=layak_page,
                                   tidak_layak=tidak_layak_page,
                                   page=page,
                                   total_pages_sangat_layak=math.ceil(len(df_sangat_layak) / per_page),
                                   total_pages_layak=math.ceil(len(df_layak) / per_page),
                                   total_pages_tidak_layak=math.ceil(len(df_tidak_layak) / per_page),
                                   active_tab=active_tab,
                                   data_loaded=data_loaded,
                                   chart_image=chart_image)
        else:
            # Mengubah pesan error agar bisa ditampilkan sebagai modal
            error = f"File {DATA_FILE} tidak ditemukan atau ada masalah saat memproses data."
            return render_template('index.html', error_file_not_found=True, data_loaded=False)

    return render_template('index.html', data_loaded=data_loaded)
    
@app.route('/detail/<int:penerima_id>')
def detail(penerima_id):
  df = klasifikasi_data()
  if df is not None:
    penerima_data = df.loc[df['id'] == penerima_id].to_dict('records')
    if penerima_data:
      return render_template('detail.html', penerima=penerima_data[0])
    else:
      flash("Penerima tidak ditemukan.", 'danger')
      return redirect(url_for('index'))
  else:
    flash("Data tidak tersedia.", 'danger')
    return redirect(url_for('index'))

# Rute untuk Tambah Data (Create) dan Tampilkan Data Mentah (Read)
@app.route('/tambah_data', methods=['GET', 'POST'])
def tambah_data():
    df = load_data_raw()
    
    if request.method == 'POST':
        try:
            # Pastikan kolom id ada dan tidak kosong untuk mendapatkan id terakhir
            if df is not None and 'id' in df.columns and not df['id'].dropna().empty:
                # Konversi ke integer sebelum mencari nilai maksimal
                df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
                new_id = df['id'].max() + 1
            else:
                new_id = 1
                df = pd.DataFrame() # Buat DataFrame kosong jika tidak ada data

            # Ambil data dari form
            new_row = {
                'id': new_id, 
                'NAMA': request.form['NAMA'], 
                'ALAMAT': request.form['ALAMAT'], 
                'NO KK.': request.form['NO KK.'],
                'pendapatan': int(request.form['pendapatan']), 
                'jumlah_anggota_keluarga': int(request.form['jumlah_anggota_keluarga']),
                'luas_rumah': f"{request.form['luas_rumah']} m²", # Simpan dalam format string 'm²'
                'status_pekerjaan': request.form['status_pekerjaan'],
                'jumlah_kendaraan': int(request.form['jumlah_kendaraan'])
            }
            new_df = pd.DataFrame([new_row])
            
            # Jika df kosong, gunakan new_df sebagai df baru, jika tidak, concat
            if df.empty and len(new_df) > 0:
                df = new_df
            elif not df.empty and len(new_df) > 0:
                 # Pastikan kolom-kolomnya sama
                df = pd.concat([df, new_df], ignore_index=True)

            # Simpan ke CSV
            df.to_csv(DATA_FILE, index=False)
            flash(f"Data {new_row['NAMA']} berhasil ditambahkan!", 'success')
            return redirect(url_for('tambah_data'))
        except Exception as e:
            flash(f"Terjadi kesalahan saat menambah data: {e}", 'danger')
            return redirect(url_for('tambah_data'))
    
    # Logic untuk menampilkan data mentah (Read)
    # Ambil query pencarian
    search_query = request.args.get('q', '').strip().lower()
    page = request.args.get('page', 1, type=int)
    per_page = 10

    data_records = []
    total = 0
    total_pages = 1
    
    if df is not None:
        # Konversi luas_rumah ke int untuk tampilan
        if 'luas_rumah' in df.columns:
            df['luas_rumah_display'] = df['luas_rumah'].astype(str).str.replace(' m²', '', regex=False).str.replace(r'\.0$', '', regex=True)
        else:
            df['luas_rumah_display'] = 'N/A' # Handle jika kolom tidak ada

        data_records = df.to_dict(orient='records')

        # Filter pencarian jika ada query
        if search_query:
            data_records = [row for row in data_records if search_query in str(row.get('NAMA','')).lower() or search_query in str(row.get('NO KK.','')).lower() or search_query in str(row.get('ALAMAT','')).lower()]

        total = len(data_records)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        start = (page - 1) * per_page
        end = start + per_page
        data_page = data_records[start:end]

        # Pastikan id integer untuk tampilan
        for row in data_records:
            if 'id' in row and row['id'] is not None:
                try:
                    row['id'] = int(row['id'])
                except Exception:
                    pass

    # Jika request AJAX, kembalikan HTML tabel saja (untuk pencarian tanpa reload)
    if request.args.get('ajax') == '1':
        from flask import jsonify, render_template_string
        table_html = """
        {% for row in data %}
        <tr>
            <td>{{ row.get('id', 'N/A') }}</td>
            <td>{{ row.get('NAMA', 'N/A') }}</td>
            <td>{{ row.get('ALAMAT', 'N/A') }}</td>
            <td>{{ row.get('NO KK.', 'N/A') }}</td>
            <td>Rp {{ "{:,.0f}".format(row.get('pendapatan', 0)) }}</td>
            <td>{{ row.get('jumlah_anggota_keluarga', 'N/A') }}</td>
            <td>{{ row.get('luas_rumah_display', 'N/A') }}</td>
            <td>{{ row.get('status_pekerjaan', 'N/A') }}</td>
            <td>{{ row.get('jumlah_kendaraan', 'N/A') }}</td>
            <td class='action-btns'>
                <a href='{{ url_for('edit_data', data_id=row.id) }}' class='btn btn-warning btn-sm' title='Edit'><i class='fas fa-edit'></i></a>
                <form method='POST' action='{{ url_for('hapus_data', data_id=row.id, page=page) }}' style='display:inline;'>
                    <button type='submit' class='btn btn-danger btn-sm' title='Hapus' onclick="return confirm('Apakah Anda yakin ingin menghapus data {{ row.NAMA }}?')"><i class='fas fa-trash-alt'></i></button>
                </form>
            </td>
        </tr>
        {% endfor %}
        """
        html = render_template_string(table_html, data=data_page, page=page)
        return jsonify({'html': html})
    return render_template('tambah_data.html', data=data_page, page=page, total_pages=total_pages, search_query=search_query)

# Rute untuk Hapus Data (Delete)
@app.route('/hapus_data/<int:data_id>', methods=['POST'])
def hapus_data(data_id):
    df = load_data_raw()
    if df is not None:
        try:
            # Pastikan 'id' adalah integer
            df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
            
            data_to_delete = df[df['id'] == data_id]
            if not data_to_delete.empty:
                nama = data_to_delete['NAMA'].iloc[0]
                df = df[df['id'] != data_id]
                df.to_csv(DATA_FILE, index=False)
                flash(f"Data {nama} (ID: {data_id}) berhasil dihapus.", 'success')
            else:
                flash(f"Data dengan ID {data_id} tidak ditemukan.", 'warning')
        except Exception as e:
            flash(f"Terjadi kesalahan saat menghapus data: {e}", 'danger')
    else:
        flash("Data tidak tersedia untuk dihapus.", 'danger')
        
    # Redirect kembali ke halaman tambah_data (bisa menyertakan halaman saat ini)
    return redirect(url_for('tambah_data', page=request.args.get('page', 1, type=int)))


# Rute untuk Edit Data (Update)
@app.route('/edit_data/<int:data_id>', methods=['GET', 'POST'])
def edit_data(data_id):
    df = load_data_raw()
    if df is None:
        flash("Data tidak tersedia untuk diubah.", 'danger')
        return redirect(url_for('tambah_data'))

    # Pastikan 'id' adalah integer
    df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
    data_index = df[df['id'] == data_id].index
    
    if data_index.empty:
        flash(f"Data dengan ID {data_id} tidak ditemukan.", 'warning')
        return redirect(url_for('tambah_data'))
    
    if request.method == 'POST':
        try:
            # Update data di DataFrame
            df.loc[data_index, 'NAMA'] = request.form['NAMA']
            df.loc[data_index, 'ALAMAT'] = request.form['ALAMAT']
            df.loc[data_index, 'NO KK.'] = request.form['NO KK.']
            df.loc[data_index, 'pendapatan'] = int(request.form['pendapatan'])
            df.loc[data_index, 'jumlah_anggota_keluarga'] = int(request.form['jumlah_anggota_keluarga'])
            df.loc[data_index, 'luas_rumah'] = f"{request.form['luas_rumah']} m²"
            df.loc[data_index, 'status_pekerjaan'] = request.form['status_pekerjaan']
            df.loc[data_index, 'jumlah_kendaraan'] = int(request.form['jumlah_kendaraan'])
            
            df.to_csv(DATA_FILE, index=False)
            flash(f"Data {request.form['NAMA']} (ID: {data_id}) berhasil diperbarui.", 'success')
            return redirect(url_for('tambah_data'))
        except Exception as e:
            flash(f"Terjadi kesalahan saat memperbarui data: {e}", 'danger')
            # Tetap di halaman edit, tapi dengan data yang dikirimkan (jika memungkinkan)
            data_to_edit = request.form
            return render_template('edit_data.html', penerima=data_to_edit, data_id=data_id)
            
    else:
        # GET request: Tampilkan form edit
        data_to_edit = df.loc[data_index].iloc[0].to_dict()
        
        # Ekstrak nilai numerik dari 'luas_rumah' untuk form input type="number"
        if 'luas_rumah' in data_to_edit and isinstance(data_to_edit['luas_rumah'], str):
            data_to_edit['luas_rumah'] = data_to_edit['luas_rumah'].replace(' m²', '').strip()
            # Konversi ke int jika memungkinkan untuk tampilan yang bersih di form
            try:
                data_to_edit['luas_rumah'] = int(float(data_to_edit['luas_rumah']))
            except ValueError:
                pass

        return render_template('edit_data.html', penerima=data_to_edit, data_id=data_id)
@app.route('/import_data', methods=['POST'])
def import_data():
    if 'file' not in request.files:
        flash('Tidak ada file yang diupload.', 'danger')
        return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '':
        flash('Nama file kosong.', 'danger')
        return redirect(url_for('index'))
    if file and file.filename.lower().endswith('.csv'):
        filename = secure_filename('sembako.csv')
        save_path = os.path.join('data', filename)
        try:
            file.save(save_path)
            flash('Data berhasil diimport!', 'success')
        except Exception as e:
            flash(f'Gagal menyimpan file: {e}', 'danger')
    else:
        flash('Format file harus .csv', 'danger')
    return redirect(url_for('index'))
    df = load_data_raw()
    if df is None:
        flash("Data tidak tersedia untuk diubah.", 'danger')
        return redirect(url_for('tambah_data'))

    # Pastikan 'id' adalah integer
    df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
    data_index = df[df['id'] == data_id].index
    
    if data_index.empty:
        flash(f"Data dengan ID {data_id} tidak ditemukan.", 'warning')
        return redirect(url_for('tambah_data'))
    
    if request.method == 'POST':
        try:
            # Update data di DataFrame
            df.loc[data_index, 'NAMA'] = request.form['NAMA']
            df.loc[data_index, 'ALAMAT'] = request.form['ALAMAT']
            df.loc[data_index, 'NO KK.'] = request.form['NO KK.']
            df.loc[data_index, 'pendapatan'] = int(request.form['pendapatan'])
            df.loc[data_index, 'jumlah_anggota_keluarga'] = int(request.form['jumlah_anggota_keluarga'])
            df.loc[data_index, 'luas_rumah'] = f"{request.form['luas_rumah']} m²"
            df.loc[data_index, 'status_pekerjaan'] = request.form['status_pekerjaan']
            df.loc[data_index, 'jumlah_kendaraan'] = int(request.form['jumlah_kendaraan'])
            
            df.to_csv(DATA_FILE, index=False)
            flash(f"Data {request.form['NAMA']} (ID: {data_id}) berhasil diperbarui.", 'success')
            return redirect(url_for('tambah_data'))
        except Exception as e:
            flash(f"Terjadi kesalahan saat memperbarui data: {e}", 'danger')
            # Tetap di halaman edit, tapi dengan data yang dikirimkan (jika memungkinkan)
            data_to_edit = request.form
            return render_template('edit_data.html', penerima=data_to_edit, data_id=data_id)
            
    else:
        # GET request: Tampilkan form edit
        data_to_edit = df.loc[data_index].iloc[0].to_dict()
        
        # Ekstrak nilai numerik dari 'luas_rumah' untuk form input type="number"
        if 'luas_rumah' in data_to_edit and isinstance(data_to_edit['luas_rumah'], str):
            data_to_edit['luas_rumah'] = data_to_edit['luas_rumah'].replace(' m²', '').strip()
            # Konversi ke int jika memungkinkan untuk tampilan yang bersih di form
            try:
                data_to_edit['luas_rumah'] = int(float(data_to_edit['luas_rumah']))
            except ValueError:
                pass

        return render_template('edit_data.html', penerima=data_to_edit, data_id=data_id)


if __name__ == '__main__':
  app.run(debug=True)