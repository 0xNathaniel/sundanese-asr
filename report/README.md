# Laporan IF4071 Fase 2

`main.tex` adalah titik masuk proyek LaTeX. Sampul mengacu pada `DOKSLI SUNDA.pdf`. Draf dapat dikompilasi saat Bab 5–8 masih diisi.

## Pembagian kerja

| Penulis | Bab | Isi |
| --- | --- | --- |
| Bagian pertama | 1–4 | Pendahuluan, tautan repositori, korpus, pemodelan, konfigurasi, implementasi, dan prapemrosesan |
| Bagian kedua | 5–8 | Eksperimen, hasil dan contoh transkripsi, analisis kesalahan, kesimpulan, keterbatasan, dan saran |

Bagian kedua dapat mengganti penanda di `chapters/05-eksperimen.tex` hingga `chapters/08-penutup.tex`. Tinjau abstrak di `frontmatter/abstrak.tex` setelah Bab 5–8 selesai dan hapus penanda drafnya saat laporan siap dikumpulkan. Tambahkan sumber yang dipakai ke `references.bib` dan pertahankan label bab agar rujukan silang tetap berfungsi.

### Sumber untuk Bab 5–8

- **Bab 5.** Gunakan notebook 01–03 di `ASR/notebooks/`, lalu cocokkan `training_config.json` dan `sweep_results.csv` pada kedua folder hasil. Skor seleksi selama pelatihan dan skor evaluasi ulang menggunakan alur penilaian yang berbeda.
- **Bab 6.** Gunakan `cahya_finetuned/model_comparison.csv`, `indonesian_nlp/validation_comparison.csv`, dan `indonesian_nlp/test_comparison.csv` di `ASR/results/`. Bukti hasil Cahya mencakup validasi. Contoh ujaran uji tersedia di `indonesian_nlp/analysis/test_per_utterance.csv`. Kurva `training_curves.png` siap dipakai dari `figures/`.
- **Bab 7.** Cocokkan jumlah substitusi, penghapusan, dan penyisipan dengan `indonesian_nlp/test_metrics.json`. Gunakan `test_top_errors.csv`, `test_rare_words.csv`, dan `test_group_metrics.csv` di folder `indonesian_nlp/analysis/` untuk rincian. Laporkan pola per kelompok dengan ukuran sampelnya.
- **Bab 8.** Tarik kesimpulan dari perbandingan *zero-shot* dan *fine-tuning* pada himpunan yang sama. Pertimbangkan keterbatasan satu pembagian berbasis penutur, status penutur jati yang tidak diketahui untuk G04, dan cakupan uji empat penutur.

## Kompilasi dengan Python

Pasang Python 3 dan TeX Live atau MiKTeX dengan `pdflatex` dan `bibtex` di `PATH`. Pustaka standar Python sudah cukup. Jika paket TeX belum tersedia, pasang paket yang dicantumkan di `main.tex` melalui distribusi TeX Anda.

Gunakan perintah ini dari root repositori.

```sh
python report/compile.py
```

Gunakan perintah ini dari folder `report/`.

```sh
python compile.py
```

PDF draf tersedia di `report/build/main.pdf` dan log di `report/build/compile.log`. Setiap build berhasil menggantikan PDF sebelumnya.

## Overleaf

Unggah `main.tex`, `references.bib`, dan folder `frontmatter/`, `chapters/`, serta `figures/` dengan struktur yang sama. Pilih `main.tex` sebagai dokumen utama dan **pdfLaTeX** sebagai kompilator.
