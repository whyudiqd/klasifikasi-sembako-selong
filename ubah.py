import csv

input_file = 'data/sembako.csv'
output_file = 'data/sembako.csv'  # overwrite original file

def update_guru_honorer(file_path):
    rows = []
    with open(file_path, mode='r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        for row in reader:
            if row['status_pekerjaan'].strip().lower() == 'guru honorer':
                row['pendapatan'] = '800000'
                row['jumlah_kendaraan'] = '1'
            rows.append(row)
    with open(file_path, mode='w', encoding='utf-8', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

if __name__ == '__main__':
    update_guru_honorer(input_file)
    print("Update selesai. File sudah diubah langsung.")