"""Utilitas FFmpeg: deteksi binary, baca durasi, dan susun perintah konversi.

Modul ini sengaja dipisah dari GUI sehingga seluruh logika di sini bisa diuji
dengan pytest tanpa perlu menjalankan jendela Tkinter.
"""

import os
import re
import shutil
import subprocess
import sys

# Ekstensi yang didukung sebagai sumber konversi.
EKSTENSI_VIDEO = ("mp4", "mkv", "avi", "mov", "webm", "flv", "wmv", "m4v", "3gp", "ts")
EKSTENSI_AUDIO = ("m4a", "aac", "wav", "flac", "ogg", "opus", "wma")
EKSTENSI_DIDUKUNG = EKSTENSI_VIDEO + EKSTENSI_AUDIO

# Bitrate yang boleh dipilih user; 192k jadi default yang seimbang.
PILIHAN_BITRATE = ("96k", "128k", "192k", "256k", "320k")
BITRATE_DEFAULT = "192k"

# Flag khusus Windows agar subprocess tidak memunculkan jendela console hitam.
CREATE_NO_WINDOW = 0x08000000


def _nama_binary_ffmpeg():
    """Nama file ffmpeg sesuai sistem operasi (ffmpeg.exe di Windows)."""
    return "ffmpeg.exe" if os.name == "nt" else "ffmpeg"


def _flag_subprocess():
    """creationflags untuk subprocess; 0 di non-Windows agar lintas-platform."""
    return CREATE_NO_WINDOW if os.name == "nt" else 0


def _folder_aplikasi():
    """Folder tempat aplikasi berjalan.

    Saat dibundle PyInstaller, file ditaruh di ``sys._MEIPASS``; selain itu kita
    pakai folder dari file executable / skrip yang sedang berjalan.
    """
    folder = []
    # Folder ekstraksi sementara milik PyInstaller (mode --onefile).
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        folder.append(meipass)
    # Folder di mana exe / skrip berada.
    if getattr(sys, "frozen", False):
        folder.append(os.path.dirname(sys.executable))
    else:
        folder.append(os.path.dirname(os.path.abspath(__file__)))
    return folder


def find_ffmpeg():
    """Cari binary FFmpeg.

    Urutan pencarian: folder aplikasi (root & ``bin/``, termasuk hasil bundle
    PyInstaller) lalu PATH sistem. Mengembalikan path string bila ketemu, atau
    ``None`` bila FFmpeg tidak tersedia di mana pun.
    """
    nama = _nama_binary_ffmpeg()

    for folder in _folder_aplikasi():
        for kandidat in (os.path.join(folder, nama), os.path.join(folder, "bin", nama)):
            if os.path.isfile(kandidat) and os.access(kandidat, os.X_OK):
                return kandidat

    # Terakhir, andalkan PATH sistem (mis. ffmpeg hasil install manual).
    di_path = shutil.which("ffmpeg")
    if di_path:
        return di_path

    return None


def parse_duration_to_seconds(teks):
    """Ubah string ``Duration: HH:MM:SS.ss`` dari output FFmpeg jadi detik (float).

    Mengembalikan ``None`` bila pola durasi tidak ditemukan (mis. file rusak).
    """
    cocok = re.search(r"Duration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)", teks)
    if not cocok:
        return None
    jam = int(cocok.group(1))
    menit = int(cocok.group(2))
    detik = float(cocok.group(3))
    return jam * 3600 + menit * 60 + detik


def parse_out_time_to_seconds(baris):
    """Baca baris ``out_time=HH:MM:SS.xx`` dari ``-progress pipe:1`` jadi detik.

    Dipakai untuk menghitung persentase progres saat konversi berjalan.
    Mengembalikan ``None`` bila baris bukan baris out_time yang valid.
    """
    cocok = re.search(r"out_time=(\d+):(\d{2}):(\d{2}(?:\.\d+)?)", baris)
    if not cocok:
        return None
    jam = int(cocok.group(1))
    menit = int(cocok.group(2))
    detik = float(cocok.group(3))
    return jam * 3600 + menit * 60 + detik


def get_duration(path_sumber, ffmpeg_path):
    """Ambil durasi file (detik) dengan menjalankan FFmpeg dan membaca stderr.

    Mengembalikan ``None`` bila durasi tidak bisa ditentukan; pemanggil sebaiknya
    tetap melanjutkan konversi walau progres tidak bisa dihitung persis.
    """
    try:
        hasil = subprocess.run(
            [ffmpeg_path, "-i", path_sumber],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=_flag_subprocess(),
        )
    except OSError:
        # FFmpeg gagal dijalankan (mis. path tidak valid) — anggap durasi tak diketahui.
        return None
    stderr = hasil.stderr.decode("utf-8", errors="replace")
    return parse_duration_to_seconds(stderr)


def build_command(path_sumber, path_tujuan, bitrate=BITRATE_DEFAULT, ffmpeg_path="ffmpeg"):
    """Susun daftar argumen perintah FFmpeg untuk konversi ke MP3.

    ``-vn`` membuang stream video, ``libmp3lame`` encoder MP3, dan
    ``-progress pipe:1`` mengalirkan progres ke stdout agar bisa diparse.
    """
    return [
        ffmpeg_path,
        "-y",                       # timpa file output sementara bila perlu
        "-i", path_sumber,
        "-vn",                      # buang video, ambil audio saja
        "-acodec", "libmp3lame",
        "-b:a", bitrate,
        "-ar", "44100",
        "-ac", "2",
        "-progress", "pipe:1",      # aliran progres ke stdout
        "-nostats",
        path_tujuan,
    ]


def unique_output_path(path_tujuan):
    """Hindari menimpa file: tambahkan ``(1)``, ``(2)``, dst. bila sudah ada.

    Contoh: ``lagu.mp3`` -> ``lagu (1).mp3`` -> ``lagu (2).mp3``.
    """
    if not os.path.exists(path_tujuan):
        return path_tujuan
    folder = os.path.dirname(path_tujuan)
    nama = os.path.basename(path_tujuan)
    dasar, ekstensi = os.path.splitext(nama)
    nomor = 1
    while True:
        kandidat = os.path.join(folder, f"{dasar} ({nomor}){ekstensi}")
        if not os.path.exists(kandidat):
            return kandidat
        nomor += 1


def is_file_didukung(path):
    """True bila ekstensi file termasuk yang didukung untuk dikonversi."""
    ekstensi = os.path.splitext(path)[1].lower().lstrip(".")
    return ekstensi in EKSTENSI_DIDUKUNG
