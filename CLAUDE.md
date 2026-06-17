# CLAUDE.md — Video ke MP3

Panduan ringkas untuk Claude Code saat bekerja di proyek ini.

## Tentang proyek

Aplikasi desktop **konverter video/audio ke MP3** yang ringan dan **offline
penuh** (tidak ada upload/server/API). Semua proses jalan di perangkat user.
Pembuat: Firdaus, PPK Politeknik KP Sorong. Target user awam.

## Stack (final, jangan diganti)

- **Python 3.10+** + **Tkinter** (GUI bawaan; tanpa Electron/Chromium).
- **FFmpeg** sebagai mesin konversi, dipanggil via `subprocess`.
- Dependensi pihak ketiga seminimal mungkin. `tkinterdnd2` **opsional** (drag &
  drop) — app harus tetap jalan bila tidak terpasang.

## Konvensi (firdaus-dev)

- Bahasa **Indonesia** untuk UI, label, pesan error, dan komentar business logic.
- **Error handling** rapi: `try/except`, status jelas, feedback Bahasa Indonesia.
  Satu file gagal **tidak boleh** menjatuhkan aplikasi — lanjut ke file berikutnya
  dan tandai "Gagal".
- **Pisahkan logika dari UI**: semua yang bisa diuji ditaruh di `core/`.
- Nama fungsi/variabel deskriptif dalam Bahasa Indonesia bila wajar; nama tes
  pytest deskriptif Bahasa Indonesia (mis. `test_durasi_diparse_dengan_benar`).

## Struktur

```
video_to_mp3.py      # entry point GUI (Tkinter, threading, queue)
core/ffmpeg_utils.py # find_ffmpeg, get_duration, build_command, unique_output_path
core/converter.py    # konversi 1 file + parsing progress + pembatalan
tests/               # pytest (tanpa GUI; tes ffmpeg nyata di-skip bila tak ada)
```

## Aturan teknis penting

- Perintah konversi:
  `ffmpeg -y -i SRC -vn -acodec libmp3lame -b:a BITRATE -ar 44100 -ac 2 -progress pipe:1 -nostats DST`
- **Windows**: semua `subprocess` pakai `creationflags=0x08000000`
  (CREATE_NO_WINDOW) agar tidak muncul console hitam. Lihat `_flag_subprocess()`.
- **Threading**: konversi di thread terpisah; UI hanya di-update dari thread
  utama lewat `queue.Queue` + `root.after()`. **Jangan** sentuh widget dari worker.
- Progres: ambil durasi via FFmpeg lalu parse baris `out_time=HH:MM:SS.xx`.
- **Batal**: hentikan proses dan hapus file MP3 parsial (`batal_event`).
- **Anti-timpa**: `unique_output_path()` menambah `(1)`, `(2)`, dst.
- **Deteksi FFmpeg**: folder app/`bin/` (cek `sys._MEIPASS` & folder exe) → PATH.

## Perintah umum

```bash
python video_to_mp3.py     # jalankan GUI
pytest                     # jalankan tes
pytest -q                  # ringkas
```

## Catatan untuk perubahan

- Bila menambah fitur konversi, taruh logikanya di `core/` + tambahkan tes.
- Jaga agar app tetap jalan tanpa `tkinterdnd2` dan tanpa FFmpeg (tampilkan
  pesan yang jelas).
- Jangan menambah dependensi berat tanpa alasan kuat.
