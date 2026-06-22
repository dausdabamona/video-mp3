# Video ke MP3

Aplikasi desktop ringan untuk mengubah file **video/audio menjadi MP3** —
berjalan **sepenuhnya offline** di perangkat Anda. Tidak ada upload, tidak ada
server, tidak ada API. Cocok untuk koneksi internet yang tidak stabil.

> Pembuat: **Firdaus**, PPK Politeknik KP Sorong.

---

## Fitur

- Tambah banyak file sekaligus (batch) lewat tombol **Tambah File** atau
  **drag & drop** (bila `tkinterdnd2` terpasang).
- Format sumber yang didukung:
  - Video: `mp4, mkv, avi, mov, webm, flv, wmv, m4v, 3gp, ts`
  - Audio: `mp3, m4a, aac, wav, flac, ogg, opus, wma`
  - Semua diubah menjadi `.mp3`.
- **Kompres MP3**: file `.mp3` yang sudah ada bisa diperkecil dengan memilih
  bitrate/kualitas yang lebih hemat (file asli tidak ditimpa).
- Dua mode kompresi:
  - **CBR** — bitrate tetap (96k / 128k / 192k / 256k / 320k, default **192k**).
  - **VBR** — kualitas variabel (`-q:a`), umumnya menghasilkan file lebih kecil
    pada kualitas setara (pilihan V0/V2/V4/V6).
- Simpan hasil di **folder sumber** atau folder pilihan sendiri.
- Konversi berjalan di **thread terpisah** sehingga jendela tidak macet.
- **Progres per-file dan total**, lengkap dengan tombol **Batal** (file MP3
  setengah jadi otomatis dihapus).
- **Anti-timpa**: bila nama hasil sudah ada, ditambahkan `(1)`, `(2)`, dst.
- Tombol **Buka Folder Hasil**.
- Pesan kesalahan jelas dalam **Bahasa Indonesia**, termasuk panduan bila
  FFmpeg belum terpasang.

---

## Kebutuhan

- **Python 3.10+** (Tkinter sudah termasuk bawaan Python).
- **FFmpeg** — mesin konversi. Aplikasi mencari FFmpeg dengan urutan:
  1. Folder aplikasi atau subfolder `bin/` (termasuk hasil bundel PyInstaller).
  2. PATH sistem.

  Bila tidak ditemukan, aplikasi menampilkan dialog berisi cara memasangnya.
- (Opsional) `tkinterdnd2` untuk fitur drag & drop:
  `pip install tkinterdnd2`

---

## Menjalankan dari sumber

```bash
python video_to_mp3.py
```

### Menaruh FFmpeg

Letakkan `ffmpeg` (atau `ffmpeg.exe` di Windows) di salah satu lokasi:

- folder yang sama dengan `video_to_mp3.py`, atau
- subfolder `bin/`, atau
- folder mana pun yang ada di PATH sistem.

Unduh FFmpeg di <https://ffmpeg.org/download.html>.

---

## Cara pakai

1. Klik **Tambah File** (atau seret file ke daftar).
2. Atur **bitrate** dan **folder hasil**.
3. Klik **Mulai Konversi**.
4. Pantau progres; gunakan **Batal** bila perlu.
5. Klik **Buka Folder Hasil** untuk melihat MP3.

---

## Pengembangan & pengujian

Logika konversi dipisah di paket `core/` agar bisa diuji tanpa GUI.

```bash
pip install pytest
pytest
```

Sebagian tes konversi nyata membutuhkan FFmpeg; tes itu otomatis dilewati bila
FFmpeg tidak tersedia.

---

## Struktur proyek

```
video-ke-mp3/
├── video_to_mp3.py        # entry point GUI
├── core/
│   ├── ffmpeg_utils.py    # find_ffmpeg, get_duration, build_command, dll.
│   └── converter.py       # konversi 1 file + parsing progress
├── tests/
│   ├── test_ffmpeg_utils.py
│   └── test_converter.py
├── requirements.txt
├── build.md               # cara build PyInstaller + Inno Setup
├── CLAUDE.md
└── README.md
```

## Membuat file `.exe`

Lihat [build.md](build.md) untuk langkah PyInstaller dan contoh installer
Inno Setup.

## Lisensi

Bebas digunakan untuk keperluan internal Politeknik KP Sorong.
