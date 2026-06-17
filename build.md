# Cara Build "Video ke MP3"

Panduan membuat aplikasi siap pakai (`.exe`) memakai **PyInstaller**, lalu
membungkusnya jadi installer dengan **Inno Setup**.

---

## 1. Persiapan

```bash
pip install pyinstaller
pip install tkinterdnd2   # opsional, bila ingin drag & drop ikut dibundel
```

Siapkan binary FFmpeg untuk platform target:

- **Windows**: `ffmpeg.exe` (unduh build statis dari <https://ffmpeg.org/download.html>).
- **Linux/macOS**: `ffmpeg`.

---

## 2. Build dengan PyInstaller

### Windows

```bat
pyinstaller --onefile --windowed --name "VideoKeMP3" ^
  --add-binary "ffmpeg.exe;." ^
  video_to_mp3.py
```

### Linux / macOS

> Catatan: pemisah pada `--add-binary` memakai **titik dua** (`:`) di Linux/macOS,
> bukan titik koma (`;`).

```bash
pyinstaller --onefile --windowed --name "VideoKeMP3" \
  --add-binary "ffmpeg:." \
  video_to_mp3.py
```

Hasil ada di folder `dist/`.

### Bila memakai drag & drop (`tkinterdnd2`)

PyInstaller umumnya mengikutkannya otomatis. Bila saat dijalankan muncul error
soal file data tkdnd, tambahkan:

```bat
--collect-all tkinterdnd2
```

### Penempatan FFmpeg di dalam bundel

Opsi `--add-binary "ffmpeg.exe;."` menaruh `ffmpeg.exe` di root folder ekstraksi
(`sys._MEIPASS`). Fungsi `find_ffmpeg()` sudah mengecek lokasi tersebut, juga
subfolder `bin/`. Bila Anda **tidak** membundel FFmpeg, aplikasi akan mencarinya
di PATH sistem dan menampilkan panduan bila tidak ada.

---

## 3. Trade-off ukuran file

| Skenario                         | Perkiraan ukuran `.exe` |
|----------------------------------|-------------------------|
| Tanpa FFmpeg dibundel            | ~10–15 MB               |
| FFmpeg ikut dibundel             | ~80–100 MB              |

- **Tanpa FFmpeg**: file kecil, mudah dibagikan, tetapi user harus menaruh
  `ffmpeg.exe` sendiri (di folder app/`bin/` atau PATH).
- **Dengan FFmpeg**: sekali jalan tanpa setup tambahan, tetapi file jauh lebih
  besar. Direkomendasikan untuk user awam.

---

## 4. Installer dengan Inno Setup (Windows)

Pasang [Inno Setup](https://jrsoftware.org/isinfo.php), simpan berkas berikut
sebagai `setup.iss`, lalu klik **Compile**. (Pola serupa e-BBM / SIPAMAN.)

```iss
; setup.iss — installer Video ke MP3
#define NamaApp "Video ke MP3"
#define VersiApp "1.0.0"
#define Penerbit "PPK Politeknik KP Sorong"
#define ExeApp "VideoKeMP3.exe"

[Setup]
AppId={{B3D9F2A1-1C2D-4E5F-9A8B-VIDEOKEMP3001}}
AppName={#NamaApp}
AppVersion={#VersiApp}
AppPublisher={#Penerbit}
DefaultDirName={autopf}\VideoKeMP3
DefaultGroupName={#NamaApp}
DisableProgramGroupPage=yes
OutputBaseFilename=VideoKeMP3-Setup-{#VersiApp}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Tidak butuh hak admin bila dipasang per-user:
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "indonesian"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Buat ikon di Desktop"; GroupDescription: "Tambahan:"

[Files]
; Hasil PyInstaller --onefile (sudah memuat ffmpeg bila dibundel)
Source: "dist\VideoKeMP3.exe"; DestDir: "{app}"; Flags: ignoreversion
; Bila FFmpeg TIDAK dibundel ke exe, sertakan terpisah di subfolder bin:
; Source: "ffmpeg.exe"; DestDir: "{app}\bin"; Flags: ignoreversion

[Icons]
Name: "{group}\{#NamaApp}"; Filename: "{app}\{#ExeApp}"
Name: "{group}\Hapus {#NamaApp}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#NamaApp}"; Filename: "{app}\{#ExeApp}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeApp}"; Description: "Jalankan {#NamaApp} sekarang"; Flags: nowait postinstall skipifsilent
```

> Bila FFmpeg tidak dibundel ke dalam `.exe`, aktifkan baris `Source: "ffmpeg.exe"...`
> di seksi `[Files]` agar `ffmpeg.exe` ikut terpasang di `{app}\bin`.

---

## 5. Uji hasil build

1. Pindahkan `dist\VideoKeMP3.exe` ke komputer **tanpa Python**.
2. Jalankan; pastikan jendela muncul (tanpa console hitam).
3. Konversi satu video kecil dan cek MP3 bisa diputar.
4. Bila muncul dialog "FFmpeg tidak ditemukan", taruh `ffmpeg.exe` di folder app
   atau subfolder `bin/`, lalu jalankan ulang.
