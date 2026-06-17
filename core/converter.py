"""Logika konversi satu file ke MP3 beserta pelaporan progres.

Modul ini tidak menyentuh widget GUI sama sekali. Komunikasi ke pemanggil
dilakukan lewat callback ``on_progress`` dan nilai kembalian ``HasilKonversi``,
sehingga GUI (thread utama) bisa memperbarui tabel lewat queue + root.after().
"""

import os
import subprocess

from core.ffmpeg_utils import (
    BITRATE_DEFAULT,
    build_command,
    get_duration,
    parse_out_time_to_seconds,
    unique_output_path,
    _flag_subprocess,
)


class Status:
    """Status sebuah pekerjaan konversi (dipakai juga sebagai label di tabel)."""

    ANTRE = "Antre"
    PROSES = "Proses"
    SELESAI = "Selesai"
    GAGAL = "Gagal"
    DIBATALKAN = "Dibatalkan"


class HasilKonversi:
    """Ringkasan hasil konversi satu file."""

    def __init__(self, status, path_tujuan=None, pesan=""):
        self.status = status
        self.path_tujuan = path_tujuan
        self.pesan = pesan

    @property
    def berhasil(self):
        return self.status == Status.SELESAI


def hitung_persen(out_time_detik, durasi_total):
    """Hitung persentase progres dari posisi waktu saat ini.

    Dibatasi 0..99 selama proses berjalan; 100 hanya ditandai saat selesai
    supaya bar tidak terlihat "penuh" padahal file belum benar-benar rampung.
    """
    if not durasi_total or durasi_total <= 0:
        return 0.0
    persen = (out_time_detik / durasi_total) * 100.0
    if persen < 0:
        return 0.0
    if persen > 99:
        return 99.0
    return persen


def _hapus_file_parsial(path):
    """Hapus file MP3 setengah jadi (mis. setelah dibatalkan/gagal)."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        # Bila gagal menghapus pun, jangan sampai aplikasi ikut crash.
        pass


def konversi_file(
    path_sumber,
    path_tujuan,
    ffmpeg_path,
    bitrate=BITRATE_DEFAULT,
    durasi=None,
    on_progress=None,
    batal_event=None,
):
    """Konversi satu file sumber menjadi MP3.

    Parameter:
        path_sumber  : file video/audio yang dikonversi.
        path_tujuan  : path MP3 yang diinginkan (akan dibuat unik bila perlu).
        ffmpeg_path  : path binary ffmpeg hasil find_ffmpeg().
        bitrate      : mis. "192k".
        durasi       : durasi detik bila sudah diketahui; bila None diambil sendiri.
        on_progress  : callback(persen: float) untuk update UI (opsional).
        batal_event  : threading.Event; bila di-set, proses dihentikan dan file
                       parsial dihapus.

    Mengembalikan HasilKonversi dengan status SELESAI / GAGAL / DIBATALKAN.
    """

    def lapor(persen):
        if on_progress:
            on_progress(persen)

    def dibatalkan():
        return batal_event is not None and batal_event.is_set()

    # Cek pembatalan sebelum mulai supaya batal di antrean tidak buang waktu.
    if dibatalkan():
        return HasilKonversi(Status.DIBATALKAN, pesan="Dibatalkan sebelum mulai.")

    if not os.path.isfile(path_sumber):
        return HasilKonversi(Status.GAGAL, pesan="File sumber tidak ditemukan.")

    # Pastikan tidak menimpa file lain.
    path_tujuan = unique_output_path(path_tujuan)

    # Durasi dipakai untuk menghitung persentase; bila gagal, progres tetap jalan
    # secara kasar (tetap 0 sampai selesai) tanpa membuat konversi batal.
    if durasi is None:
        durasi = get_duration(path_sumber, ffmpeg_path)

    perintah = build_command(path_sumber, path_tujuan, bitrate=bitrate, ffmpeg_path=ffmpeg_path)

    try:
        proses = subprocess.Popen(
            perintah,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,   # gabung log ffmpeg ke satu aliran (hindari deadlock pipe)
            universal_newlines=True,
            bufsize=1,
            creationflags=_flag_subprocess(),
        )
    except OSError as e:
        return HasilKonversi(Status.GAGAL, pesan=f"Gagal menjalankan FFmpeg: {e}")

    # Simpan beberapa baris terakhir untuk pesan error bila konversi gagal.
    ekor_log = []
    lapor(0.0)

    try:
        for baris in proses.stdout:
            if dibatalkan():
                _hentikan_proses(proses)
                _hapus_file_parsial(path_tujuan)
                return HasilKonversi(Status.DIBATALKAN, pesan="Konversi dibatalkan.")

            baris = baris.strip()
            if not baris:
                continue
            ekor_log.append(baris)
            if len(ekor_log) > 15:
                ekor_log.pop(0)

            detik = parse_out_time_to_seconds(baris)
            if detik is not None:
                lapor(hitung_persen(detik, durasi))
    finally:
        if proses.stdout:
            proses.stdout.close()

    proses.wait()

    # Pembatalan bisa terjadi tepat setelah loop selesai.
    if dibatalkan():
        _hapus_file_parsial(path_tujuan)
        return HasilKonversi(Status.DIBATALKAN, pesan="Konversi dibatalkan.")

    if proses.returncode != 0:
        _hapus_file_parsial(path_tujuan)
        pesan = "\n".join(ekor_log[-5:]) or "FFmpeg keluar dengan kode error."
        return HasilKonversi(Status.GAGAL, pesan=pesan)

    # Verifikasi file output benar-benar ada dan tidak kosong.
    if not os.path.exists(path_tujuan) or os.path.getsize(path_tujuan) == 0:
        _hapus_file_parsial(path_tujuan)
        return HasilKonversi(Status.GAGAL, pesan="File MP3 tidak terbentuk.")

    lapor(100.0)
    return HasilKonversi(Status.SELESAI, path_tujuan=path_tujuan, pesan="Selesai.")


def _hentikan_proses(proses):
    """Hentikan proses ffmpeg dengan rapi; paksa kill bila tidak mau berhenti."""
    try:
        proses.terminate()
        proses.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proses.kill()
        proses.wait()
    except OSError:
        pass
