"""Video ke MP3 — aplikasi desktop konverter offline.

Pembuat: Firdaus, PPK Politeknik KP Sorong.
Seluruh proses berjalan di perangkat user; tidak ada upload/server/API.

UI memakai Tkinter (bawaan Python). Drag & drop opsional lewat tkinterdnd2 —
bila pustaka itu tidak terpasang, aplikasi tetap berjalan memakai tombol
"Tambah File".

Aturan threading: konversi berjalan di thread terpisah. Thread pekerja TIDAK
boleh menyentuh widget langsung; semua kabar ke UI dikirim lewat queue.Queue
dan diproses di thread utama lewat root.after().
"""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core import converter, ffmpeg_utils
from core.ffmpeg_utils import (
    BITRATE_DEFAULT,
    EKSTENSI_DIDUKUNG,
    KUALITAS_VBR_DEFAULT,
    MODE_CBR,
    MODE_VBR,
    PILIHAN_BITRATE,
    PILIHAN_KUALITAS_VBR,
    is_file_didukung,
)

# Coba aktifkan drag & drop; aplikasi tetap jalan walau pustaka tidak ada.
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    DND_TERSEDIA = True
except ImportError:
    DND_TERSEDIA = False

JUDUL_APP = "Video ke MP3"


def buka_folder(path):
    """Buka folder di file manager sistem (lintas-platform)."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa: F821 (hanya ada di Windows)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError:
        pass


class PekerjaanFile:
    """Satu baris pekerjaan: file sumber, status, dan progres."""

    def __init__(self, iid, path_sumber):
        self.iid = iid
        self.path_sumber = path_sumber
        self.status = converter.Status.ANTRE
        self.persen = 0.0
        self.path_hasil = None
        self.pesan = ""


class AplikasiVideoKeMP3:
    def __init__(self, root):
        self.root = root
        self.root.title(JUDUL_APP)
        self.root.geometry("760x560")
        self.root.minsize(640, 480)

        # Antrean pesan dari thread pekerja menuju thread UI.
        self.antrean = queue.Queue()
        self.pekerjaan = {}          # iid -> PekerjaanFile
        self.thread_konversi = None
        self.batal_event = threading.Event()
        self.sedang_konversi = False
        self._penghitung_iid = 0

        # Deteksi ffmpeg sekali di awal.
        self.ffmpeg_path = ffmpeg_utils.find_ffmpeg()

        self._bangun_ui()
        self._aktifkan_dnd()

        if self.ffmpeg_path is None:
            self.root.after(300, self._dialog_ffmpeg_hilang)

        # Mulai polling antrean UI.
        self.root.after(100, self._proses_antrean)

    # ----------------------------------------------------------------- UI ---
    def _bangun_ui(self):
        # --- Bilah atas: tombol tambah file & opsi ---
        bingkai_atas = ttk.Frame(self.root, padding=10)
        bingkai_atas.pack(fill="x")

        ttk.Button(bingkai_atas, text="Tambah File", command=self.tambah_file).pack(
            side="left"
        )
        ttk.Button(bingkai_atas, text="Hapus Terpilih", command=self.hapus_terpilih).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(bingkai_atas, text="Bersihkan", command=self.bersihkan).pack(
            side="left", padx=(8, 0)
        )

        # --- Tabel daftar file ---
        bingkai_tabel = ttk.Frame(self.root, padding=(10, 0))
        bingkai_tabel.pack(fill="both", expand=True)

        kolom = ("nama", "status", "progres")
        self.tabel = ttk.Treeview(
            bingkai_tabel, columns=kolom, show="headings", selectmode="extended"
        )
        self.tabel.heading("nama", text="Nama File")
        self.tabel.heading("status", text="Status")
        self.tabel.heading("progres", text="Progres")
        self.tabel.column("nama", width=440, anchor="w")
        self.tabel.column("status", width=120, anchor="center")
        self.tabel.column("progres", width=100, anchor="center")

        gulir = ttk.Scrollbar(bingkai_tabel, orient="vertical", command=self.tabel.yview)
        self.tabel.configure(yscrollcommand=gulir.set)
        self.tabel.pack(side="left", fill="both", expand=True)
        gulir.pack(side="right", fill="y")

        # --- Opsi konversi ---
        bingkai_opsi = ttk.LabelFrame(self.root, text="Opsi", padding=10)
        bingkai_opsi.pack(fill="x", padx=10, pady=(10, 0))

        # --- Mode kompresi: bitrate tetap (CBR) atau kualitas variabel (VBR) ---
        self.var_mode = tk.StringVar(value=MODE_CBR)
        ttk.Label(bingkai_opsi, text="Mode:").grid(row=0, column=0, sticky="w")
        bingkai_mode = ttk.Frame(bingkai_opsi)
        bingkai_mode.grid(row=0, column=1, columnspan=3, sticky="w")
        ttk.Radiobutton(
            bingkai_mode, text="Bitrate tetap (CBR)", value=MODE_CBR,
            variable=self.var_mode, command=self._perbarui_status_mode,
        ).pack(side="left")
        ttk.Radiobutton(
            bingkai_mode, text="Kualitas/kompres (VBR)", value=MODE_VBR,
            variable=self.var_mode, command=self._perbarui_status_mode,
        ).pack(side="left", padx=(12, 0))

        # Bitrate (dipakai pada mode CBR).
        ttk.Label(bingkai_opsi, text="Bitrate:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.var_bitrate = tk.StringVar(value=BITRATE_DEFAULT)
        self.combo_bitrate = ttk.Combobox(
            bingkai_opsi,
            textvariable=self.var_bitrate,
            values=list(PILIHAN_BITRATE),
            state="readonly",
            width=8,
        )
        self.combo_bitrate.grid(row=1, column=1, sticky="w", padx=(6, 20), pady=(8, 0))

        # Kualitas VBR (dipakai pada mode VBR). Combobox menampilkan label ramah,
        # nilai -q:a sebenarnya dipetakan lewat _kualitas_vbr_terpilih().
        ttk.Label(bingkai_opsi, text="Kualitas:").grid(row=1, column=2, sticky="e", pady=(8, 0))
        self._label_vbr_ke_nilai = {label: nilai for label, nilai in PILIHAN_KUALITAS_VBR}
        label_default = next(
            label for label, nilai in PILIHAN_KUALITAS_VBR if nilai == KUALITAS_VBR_DEFAULT
        )
        self.var_kualitas = tk.StringVar(value=label_default)
        self.combo_kualitas = ttk.Combobox(
            bingkai_opsi,
            textvariable=self.var_kualitas,
            values=[label for label, _ in PILIHAN_KUALITAS_VBR],
            state="readonly",
            width=22,
        )
        self.combo_kualitas.grid(row=1, column=3, sticky="w", padx=(6, 0), pady=(8, 0))

        self.var_sama_sumber = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            bingkai_opsi,
            text="Simpan di folder yang sama dengan sumber",
            variable=self.var_sama_sumber,
            command=self._perbarui_status_folder,
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))

        ttk.Label(bingkai_opsi, text="Folder hasil:").grid(
            row=3, column=0, sticky="w", pady=(8, 0)
        )
        self.var_folder = tk.StringVar(value="")
        self.entri_folder = ttk.Entry(bingkai_opsi, textvariable=self.var_folder, width=50)
        self.entri_folder.grid(row=3, column=1, columnspan=2, sticky="we", pady=(8, 0))
        self.tombol_pilih_folder = ttk.Button(
            bingkai_opsi, text="Pilih…", command=self.pilih_folder_hasil
        )
        self.tombol_pilih_folder.grid(row=3, column=3, padx=(6, 0), pady=(8, 0))
        bingkai_opsi.columnconfigure(1, weight=1)
        self._perbarui_status_folder()
        self._perbarui_status_mode()

        # --- Progres total ---
        bingkai_progres = ttk.Frame(self.root, padding=(10, 8))
        bingkai_progres.pack(fill="x")
        self.label_progres = ttk.Label(bingkai_progres, text="Siap.")
        self.label_progres.pack(side="top", anchor="w")
        self.progres_total = ttk.Progressbar(
            bingkai_progres, orient="horizontal", mode="determinate", maximum=100
        )
        self.progres_total.pack(side="top", fill="x", pady=(4, 0))

        # --- Tombol aksi bawah ---
        bingkai_bawah = ttk.Frame(self.root, padding=10)
        bingkai_bawah.pack(fill="x")
        self.tombol_konversi = ttk.Button(
            bingkai_bawah, text="Mulai Konversi", command=self.mulai_konversi
        )
        self.tombol_konversi.pack(side="left")
        self.tombol_batal = ttk.Button(
            bingkai_bawah, text="Batal", command=self.batalkan, state="disabled"
        )
        self.tombol_batal.pack(side="left", padx=(8, 0))
        self.tombol_buka = ttk.Button(
            bingkai_bawah, text="Buka Folder Hasil", command=self.buka_folder_hasil
        )
        self.tombol_buka.pack(side="left", padx=(8, 0))

        info = "Drag & drop aktif." if DND_TERSEDIA else "Drag & drop nonaktif (pakai tombol Tambah File)."
        ttk.Label(bingkai_bawah, text=info).pack(side="right")

    def _aktifkan_dnd(self):
        if not DND_TERSEDIA:
            return
        try:
            self.tabel.drop_target_register(DND_FILES)
            self.tabel.dnd_bind("<<Drop>>", self._pada_drop)
        except tk.TclError:
            pass

    def _pada_drop(self, event):
        # event.data berisi daftar path; bisa dibungkus kurung kurawal bila ada spasi.
        path_list = self.root.tk.splitlist(event.data)
        self._tambah_path_list(path_list)

    # ------------------------------------------------------------ tindakan ---
    def _iid_baru(self):
        self._penghitung_iid += 1
        return f"file{self._penghitung_iid}"

    def tambah_file(self):
        pola = " ".join(f"*.{e}" for e in EKSTENSI_DIDUKUNG)
        path_list = filedialog.askopenfilenames(
            title="Pilih file video/audio",
            filetypes=[("File didukung", pola), ("Semua file", "*.*")],
        )
        self._tambah_path_list(path_list)

    def _tambah_path_list(self, path_list):
        ditolak = 0
        sudah_ada = {p.path_sumber for p in self.pekerjaan.values()}
        for path in path_list:
            path = os.path.abspath(path)
            if not os.path.isfile(path):
                continue
            if not is_file_didukung(path):
                ditolak += 1
                continue
            if path in sudah_ada:
                continue
            iid = self._iid_baru()
            pekerjaan = PekerjaanFile(iid, path)
            self.pekerjaan[iid] = pekerjaan
            sudah_ada.add(path)
            self.tabel.insert(
                "", "end", iid=iid,
                values=(os.path.basename(path), pekerjaan.status, "0%"),
            )
        if ditolak:
            messagebox.showwarning(
                JUDUL_APP,
                f"{ditolak} file dilewati karena format tidak didukung.",
            )

    def hapus_terpilih(self):
        if self.sedang_konversi:
            messagebox.showinfo(JUDUL_APP, "Tidak bisa menghapus saat konversi berjalan.")
            return
        for iid in self.tabel.selection():
            self.tabel.delete(iid)
            self.pekerjaan.pop(iid, None)

    def bersihkan(self):
        if self.sedang_konversi:
            messagebox.showinfo(JUDUL_APP, "Tidak bisa membersihkan saat konversi berjalan.")
            return
        for iid in list(self.pekerjaan):
            self.tabel.delete(iid)
        self.pekerjaan.clear()
        self.progres_total["value"] = 0
        self.label_progres.config(text="Siap.")

    def _perbarui_status_folder(self):
        aktif = not self.var_sama_sumber.get()
        keadaan = "normal" if aktif else "disabled"
        self.entri_folder.config(state=keadaan)
        self.tombol_pilih_folder.config(state=keadaan)

    def _perbarui_status_mode(self):
        # Aktifkan kontrol sesuai mode: CBR -> bitrate, VBR -> kualitas.
        vbr = self.var_mode.get() == MODE_VBR
        self.combo_bitrate.config(state="disabled" if vbr else "readonly")
        self.combo_kualitas.config(state="readonly" if vbr else "disabled")

    def _kualitas_vbr_terpilih(self):
        """Petakan label combobox kualitas ke nilai -q:a libmp3lame."""
        return self._label_vbr_ke_nilai.get(self.var_kualitas.get(), KUALITAS_VBR_DEFAULT)

    def pilih_folder_hasil(self):
        folder = filedialog.askdirectory(title="Pilih folder hasil")
        if folder:
            self.var_folder.set(folder)

    def buka_folder_hasil(self):
        # Buka folder hasil dari file yang sudah selesai, atau folder yang dipilih.
        target = None
        for pekerjaan in self.pekerjaan.values():
            if pekerjaan.path_hasil:
                target = os.path.dirname(pekerjaan.path_hasil)
                break
        if target is None:
            if not self.var_sama_sumber.get() and self.var_folder.get():
                target = self.var_folder.get()
        if target and os.path.isdir(target):
            buka_folder(target)
        else:
            messagebox.showinfo(JUDUL_APP, "Belum ada folder hasil untuk dibuka.")

    # ------------------------------------------------------------- konversi ---
    def _folder_tujuan_untuk(self, path_sumber):
        if self.var_sama_sumber.get():
            return os.path.dirname(path_sumber)
        return self.var_folder.get()

    def mulai_konversi(self):
        if self.sedang_konversi:
            return
        if self.ffmpeg_path is None:
            self._dialog_ffmpeg_hilang()
            return
        if not self.pekerjaan:
            messagebox.showinfo(JUDUL_APP, "Belum ada file untuk dikonversi.")
            return

        if not self.var_sama_sumber.get():
            folder = self.var_folder.get()
            if not folder or not os.path.isdir(folder):
                messagebox.showwarning(JUDUL_APP, "Pilih folder hasil yang valid dulu.")
                return

        # Reset status semua pekerjaan ke Antre.
        for pekerjaan in self.pekerjaan.values():
            pekerjaan.status = converter.Status.ANTRE
            pekerjaan.persen = 0.0
            pekerjaan.path_hasil = None
            self._set_baris(pekerjaan)

        self.batal_event.clear()
        self.sedang_konversi = True
        self._kunci_kontrol(True)
        self.progres_total["value"] = 0
        self.label_progres.config(text="Memulai konversi…")

        # Salin daftar pekerjaan + opsi agar thread tidak baca widget.
        daftar = [
            (p.iid, p.path_sumber, self._folder_tujuan_untuk(p.path_sumber))
            for p in self.pekerjaan.values()
        ]
        bitrate = self.var_bitrate.get()
        mode = self.var_mode.get()
        kualitas_vbr = self._kualitas_vbr_terpilih()
        self.thread_konversi = threading.Thread(
            target=self._worker, args=(daftar, bitrate, mode, kualitas_vbr), daemon=True
        )
        self.thread_konversi.start()

    def _worker(self, daftar, bitrate, mode, kualitas_vbr):
        """Berjalan di thread terpisah. Hanya berkomunikasi lewat self.antrean."""
        total = len(daftar)
        for indeks, (iid, sumber, folder_tujuan) in enumerate(daftar):
            if self.batal_event.is_set():
                self.antrean.put(("status", iid, converter.Status.DIBATALKAN, None))
                continue

            self.antrean.put(("status", iid, converter.Status.PROSES, None))
            dasar = os.path.splitext(os.path.basename(sumber))[0] + ".mp3"
            tujuan = os.path.join(folder_tujuan, dasar)

            def on_progress(persen, _iid=iid, _indeks=indeks, _total=total):
                self.antrean.put(("progress", _iid, persen, (_indeks, _total)))

            try:
                hasil = converter.konversi_file(
                    sumber, tujuan, self.ffmpeg_path,
                    bitrate=bitrate, on_progress=on_progress,
                    batal_event=self.batal_event,
                    mode=mode, kualitas_vbr=kualitas_vbr,
                )
            except Exception as e:  # jaring pengaman: 1 file gagal jangan jatuhkan app
                hasil = converter.HasilKonversi(converter.Status.GAGAL, pesan=str(e))

            self.antrean.put(("selesai", iid, hasil, (indeks, total)))

        self.antrean.put(("done", None, None, None))

    def batalkan(self):
        if self.sedang_konversi:
            self.batal_event.set()
            self.label_progres.config(text="Membatalkan…")
            self.tombol_batal.config(state="disabled")

    # --------------------------------------------------------- antrean UI ---
    def _proses_antrean(self):
        try:
            while True:
                jenis, iid, data, ekstra = self.antrean.get_nowait()
                if jenis == "status":
                    pekerjaan = self.pekerjaan.get(iid)
                    if pekerjaan:
                        pekerjaan.status = data
                        self._set_baris(pekerjaan)
                elif jenis == "progress":
                    pekerjaan = self.pekerjaan.get(iid)
                    if pekerjaan:
                        pekerjaan.persen = data
                        self._set_baris(pekerjaan)
                        self._perbarui_progres_total(ekstra, data)
                elif jenis == "selesai":
                    self._tangani_selesai(iid, data, ekstra)
                elif jenis == "done":
                    self._konversi_kelar()
        except queue.Empty:
            pass
        self.root.after(100, self._proses_antrean)

    def _tangani_selesai(self, iid, hasil, ekstra):
        pekerjaan = self.pekerjaan.get(iid)
        if not pekerjaan:
            return
        pekerjaan.status = hasil.status
        pekerjaan.pesan = hasil.pesan
        pekerjaan.path_hasil = hasil.path_tujuan
        pekerjaan.persen = 100.0 if hasil.berhasil else pekerjaan.persen
        self._set_baris(pekerjaan)
        if ekstra:
            indeks, total = ekstra
            self.progres_total["value"] = (indeks + 1) / total * 100

    def _perbarui_progres_total(self, ekstra, persen_file):
        if not ekstra:
            return
        indeks, total = ekstra
        # Total = file yang sudah lewat + fraksi file yang sedang berjalan.
        nilai = (indeks + persen_file / 100.0) / total * 100
        self.progres_total["value"] = nilai
        self.label_progres.config(text=f"Memproses file {indeks + 1} dari {total}…")

    def _konversi_kelar(self):
        self.sedang_konversi = False
        self._kunci_kontrol(False)
        selesai = sum(1 for p in self.pekerjaan.values() if p.status == converter.Status.SELESAI)
        gagal = sum(1 for p in self.pekerjaan.values() if p.status == converter.Status.GAGAL)
        dibatalkan = sum(
            1 for p in self.pekerjaan.values() if p.status == converter.Status.DIBATALKAN
        )
        self.progres_total["value"] = 100 if not dibatalkan else self.progres_total["value"]
        ringkas = f"Selesai: {selesai} berhasil, {gagal} gagal"
        if dibatalkan:
            ringkas += f", {dibatalkan} dibatalkan"
        self.label_progres.config(text=ringkas + ".")

        if gagal:
            pesan_gagal = "\n".join(
                f"• {os.path.basename(p.path_sumber)}: {p.pesan.splitlines()[-1] if p.pesan else ''}"
                for p in self.pekerjaan.values()
                if p.status == converter.Status.GAGAL
            )
            messagebox.showwarning(JUDUL_APP, "Beberapa file gagal:\n" + pesan_gagal)

    def _set_baris(self, pekerjaan):
        self.tabel.item(
            pekerjaan.iid,
            values=(
                os.path.basename(pekerjaan.path_sumber),
                pekerjaan.status,
                f"{int(pekerjaan.persen)}%",
            ),
        )

    def _kunci_kontrol(self, mengunci):
        self.tombol_konversi.config(state="disabled" if mengunci else "normal")
        self.tombol_batal.config(state="normal" if mengunci else "disabled")

    # --------------------------------------------------------------- dialog ---
    def _dialog_ffmpeg_hilang(self):
        nama = ffmpeg_utils._nama_binary_ffmpeg()
        pesan = (
            "FFmpeg tidak ditemukan, sehingga konversi belum bisa dijalankan.\n\n"
            "Cara mengatasi:\n"
            f"1. Unduh FFmpeg dari https://ffmpeg.org/download.html\n"
            f"2. Letakkan file '{nama}' di folder aplikasi ini "
            "(atau di subfolder 'bin/').\n"
            "3. Atau pasang FFmpeg lalu tambahkan ke PATH sistem.\n\n"
            "Setelah itu, buka kembali aplikasi ini."
        )
        messagebox.showerror(JUDUL_APP, pesan)


def main():
    if DND_TERSEDIA:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    AplikasiVideoKeMP3(root)
    root.mainloop()


if __name__ == "__main__":
    main()
