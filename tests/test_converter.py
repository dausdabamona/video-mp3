"""Uji untuk core.converter.

Tes hitung_persen & pembersihan file tidak butuh ffmpeg. Tes konversi nyata
otomatis dilewati (skip) bila ffmpeg tidak tersedia di lingkungan tes.
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import converter, ffmpeg_utils  # noqa: E402


# --- hitung_persen ---------------------------------------------------------

def test_persen_setengah_durasi():
    assert converter.hitung_persen(30, 60) == pytest.approx(50.0)


def test_persen_dibatasi_maksimal_99_saat_proses():
    # Walau out_time melebihi durasi, jangan tampilkan 100 sebelum benar selesai.
    assert converter.hitung_persen(120, 60) == 99.0


def test_persen_nol_bila_durasi_tidak_diketahui():
    assert converter.hitung_persen(10, None) == 0.0
    assert converter.hitung_persen(10, 0) == 0.0


def test_persen_tidak_negatif():
    assert converter.hitung_persen(-5, 60) == 0.0


# --- pembersihan file parsial ---------------------------------------------

def test_hapus_file_parsial_menghapus_file_yang_ada(tmp_path):
    f = tmp_path / "parsial.mp3"
    f.write_text("isi setengah")
    converter._hapus_file_parsial(str(f))
    assert not f.exists()


def test_hapus_file_parsial_aman_bila_file_tidak_ada(tmp_path):
    # Tidak boleh melempar error walau file tidak ada.
    converter._hapus_file_parsial(str(tmp_path / "tidakada.mp3"))


# --- gagal tanpa ffmpeg ----------------------------------------------------

def test_konversi_gagal_bila_sumber_tidak_ada(tmp_path):
    hasil = converter.konversi_file(
        str(tmp_path / "tidakada.mp4"),
        str(tmp_path / "keluar.mp3"),
        ffmpeg_path="ffmpeg",
    )
    assert hasil.status == converter.Status.GAGAL


# --- tes integrasi nyata (butuh ffmpeg) ------------------------------------

ffmpeg_path = ffmpeg_utils.find_ffmpeg()
butuh_ffmpeg = pytest.mark.skipif(ffmpeg_path is None, reason="ffmpeg tidak tersedia")


def _buat_video_uji(path, ffmpeg, durasi=1):
    """Buat video uji sintetis (video testsrc + audio sine) memakai ffmpeg."""
    subprocess.run(
        [
            ffmpeg, "-y",
            "-f", "lavfi", "-i", f"testsrc=duration={durasi}:size=160x120:rate=15",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={durasi}",
            "-shortest", path,
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
    )


@butuh_ffmpeg
def test_konversi_video_kecil_menghasilkan_mp3_valid(tmp_path):
    sumber = str(tmp_path / "uji.mp4")
    _buat_video_uji(sumber, ffmpeg_path, durasi=1)

    progres_terlihat = []
    hasil = converter.konversi_file(
        sumber,
        str(tmp_path / "uji.mp3"),
        ffmpeg_path=ffmpeg_path,
        bitrate="128k",
        on_progress=progres_terlihat.append,
    )

    assert hasil.status == converter.Status.SELESAI
    assert os.path.exists(hasil.path_tujuan)
    assert os.path.getsize(hasil.path_tujuan) > 0
    # Progres harus melaporkan 100 di akhir.
    assert progres_terlihat[-1] == 100.0
    # MP3 hasil harus punya durasi yang bisa dibaca (kira-kira 1 detik).
    durasi = ffmpeg_utils.get_duration(hasil.path_tujuan, ffmpeg_path)
    assert durasi is not None and durasi > 0.5


@butuh_ffmpeg
def test_konversi_anti_timpa_membuat_file_kedua(tmp_path):
    sumber = str(tmp_path / "uji.mp4")
    _buat_video_uji(sumber, ffmpeg_path, durasi=1)
    target = str(tmp_path / "uji.mp3")

    hasil1 = converter.konversi_file(sumber, target, ffmpeg_path=ffmpeg_path, bitrate="128k")
    hasil2 = converter.konversi_file(sumber, target, ffmpeg_path=ffmpeg_path, bitrate="128k")

    assert hasil1.path_tujuan == target
    assert hasil2.path_tujuan == str(tmp_path / "uji (1).mp3")
    assert os.path.exists(hasil2.path_tujuan)


@butuh_ffmpeg
def test_batal_menghapus_file_parsial(tmp_path):
    import threading

    # Video agak panjang supaya sempat dibatalkan di tengah jalan.
    sumber = str(tmp_path / "panjang.mp4")
    _buat_video_uji(sumber, ffmpeg_path, durasi=8)
    target = str(tmp_path / "panjang.mp3")

    batal = threading.Event()
    batal.set()  # batalkan langsung sebelum mulai

    hasil = converter.konversi_file(
        sumber, target, ffmpeg_path=ffmpeg_path, bitrate="128k", batal_event=batal,
    )
    assert hasil.status == converter.Status.DIBATALKAN
    assert not os.path.exists(target)
