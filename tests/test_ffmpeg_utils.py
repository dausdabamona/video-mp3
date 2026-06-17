"""Uji unit untuk core.ffmpeg_utils (tanpa GUI, tanpa butuh ffmpeg asli)."""

import os
import sys

import pytest

# Pastikan paket core bisa diimpor saat pytest dijalankan dari root proyek.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import ffmpeg_utils  # noqa: E402


# --- find_ffmpeg -----------------------------------------------------------

def test_find_ffmpeg_mengembalikan_path_bila_ada_di_folder_app(tmp_path, monkeypatch):
    nama = ffmpeg_utils._nama_binary_ffmpeg()
    palsu = tmp_path / nama
    palsu.write_text("biner palsu")
    palsu.chmod(0o755)
    # Paksa folder aplikasi menunjuk ke tmp_path.
    monkeypatch.setattr(ffmpeg_utils, "_folder_aplikasi", lambda: [str(tmp_path)])
    assert ffmpeg_utils.find_ffmpeg() == str(palsu)


def test_find_ffmpeg_juga_mencari_di_subfolder_bin(tmp_path, monkeypatch):
    nama = ffmpeg_utils._nama_binary_ffmpeg()
    folder_bin = tmp_path / "bin"
    folder_bin.mkdir()
    palsu = folder_bin / nama
    palsu.write_text("biner palsu")
    palsu.chmod(0o755)
    monkeypatch.setattr(ffmpeg_utils, "_folder_aplikasi", lambda: [str(tmp_path)])
    assert ffmpeg_utils.find_ffmpeg() == str(palsu)


def test_find_ffmpeg_mengembalikan_none_bila_tidak_ada(tmp_path, monkeypatch):
    monkeypatch.setattr(ffmpeg_utils, "_folder_aplikasi", lambda: [str(tmp_path)])
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda _nama: None)
    assert ffmpeg_utils.find_ffmpeg() is None


# --- parse durasi ----------------------------------------------------------

def test_durasi_diparse_dengan_benar():
    teks = "  Duration: 00:01:30.50, start: 0.000000, bitrate: 128 kb/s"
    assert ffmpeg_utils.parse_duration_to_seconds(teks) == pytest.approx(90.5)


def test_durasi_lebih_dari_satu_jam_diparse_benar():
    teks = "Duration: 01:02:03.00,"
    assert ffmpeg_utils.parse_duration_to_seconds(teks) == pytest.approx(3723.0)


def test_durasi_tanpa_desimal_diparse_benar():
    teks = "Duration: 00:00:05,"
    assert ffmpeg_utils.parse_duration_to_seconds(teks) == pytest.approx(5.0)


def test_durasi_tidak_ditemukan_mengembalikan_none():
    assert ffmpeg_utils.parse_duration_to_seconds("tidak ada durasi di sini") is None


def test_out_time_progress_diparse_benar():
    assert ffmpeg_utils.parse_out_time_to_seconds("out_time=00:00:10.25") == pytest.approx(10.25)


def test_out_time_baris_lain_mengembalikan_none():
    assert ffmpeg_utils.parse_out_time_to_seconds("frame=10 fps=25") is None


# --- unique_output_path ----------------------------------------------------

def test_unique_output_path_mengembalikan_path_asli_bila_belum_ada(tmp_path):
    target = str(tmp_path / "lagu.mp3")
    assert ffmpeg_utils.unique_output_path(target) == target


def test_unique_output_path_menambah_angka_satu_saat_file_sudah_ada(tmp_path):
    asli = tmp_path / "lagu.mp3"
    asli.write_text("isi")
    hasil = ffmpeg_utils.unique_output_path(str(asli))
    assert hasil == str(tmp_path / "lagu (1).mp3")


def test_unique_output_path_menaikkan_angka_saat_beberapa_sudah_ada(tmp_path):
    (tmp_path / "lagu.mp3").write_text("isi")
    (tmp_path / "lagu (1).mp3").write_text("isi")
    hasil = ffmpeg_utils.unique_output_path(str(tmp_path / "lagu.mp3"))
    assert hasil == str(tmp_path / "lagu (2).mp3")


# --- build_command ---------------------------------------------------------

def test_build_command_memuat_vn_dan_libmp3lame():
    perintah = ffmpeg_utils.build_command("masuk.mp4", "keluar.mp3")
    assert "-vn" in perintah
    assert "libmp3lame" in perintah


def test_build_command_memakai_bitrate_yang_diberikan():
    perintah = ffmpeg_utils.build_command("masuk.mp4", "keluar.mp3", bitrate="320k")
    idx = perintah.index("-b:a")
    assert perintah[idx + 1] == "320k"


def test_build_command_default_bitrate_192k():
    perintah = ffmpeg_utils.build_command("masuk.mp4", "keluar.mp3")
    idx = perintah.index("-b:a")
    assert perintah[idx + 1] == "192k"


def test_build_command_sumber_dan_tujuan_serta_progress_pipe():
    perintah = ffmpeg_utils.build_command("masuk.mp4", "keluar.mp3", ffmpeg_path="/usr/bin/ffmpeg")
    assert perintah[0] == "/usr/bin/ffmpeg"
    assert "masuk.mp4" in perintah
    assert perintah[-1] == "keluar.mp3"
    assert "pipe:1" in perintah


# --- is_file_didukung ------------------------------------------------------

def test_is_file_didukung_menerima_video_dan_audio():
    assert ffmpeg_utils.is_file_didukung("video.MP4")
    assert ffmpeg_utils.is_file_didukung("suara.flac")


def test_is_file_didukung_menolak_ekstensi_lain():
    assert not ffmpeg_utils.is_file_didukung("dokumen.pdf")
