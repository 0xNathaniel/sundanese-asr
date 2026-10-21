# Korpus Ucapan Bahasa Sunda

Korpus ucapan bahasa Sunda dari 10 penutur, dikumpulkan untuk tugas besar IF4071 Pemrosesan Ucapan (Fase 1) sebagai data pengembangan sistem pengenal ucapan (ASR) pada Fase 2.

> **Catatan:** Data hanya untuk keperluan akademik dan tidak untuk tujuan komersial.

---

## Ringkasan

| Aspek | Keterangan |
|---|---|
| Bahasa | Sunda |
| Jenis ucapan | Spontan, kecuali S01 dan S02 (penutur non-native) yang membacakan skrip |
| Penutur | 10 (5 laki-laki, 5 perempuan), usia 15–51 tahun |
| Jumlah segmen | 750 (satu file = satu utterance) |
| Total durasi | 116,5 menit (±1,9 jam) |
| Durasi per segmen | 2,8–22,3 detik (rata-rata 9,3, median 9,1) |
| Format audio | WAV, 16 kHz, 16-bit, mono |
| Topik | 5 (Daily, Family, Food, Work_Education, Hobby) |
| Kualitas | 679 Good (90,5%), 71 Acceptable (9,5%), 0 Reject |
| Waktu perekaman | 17–20 Oktober 2026 |

---

## Struktur Repositori

```
Korpus_Bahasa_Sunda/
├── audio/            # file WAV per penutur (S01–S10)
├── metadata/         # metadata.csv
├── annotation/       # annotation.csv
├── consent/
│   └── consent_form/ # formulir persetujuan penutur
└── documentation/    # README ini
```

| Folder | Isi |
|---|---|
| `audio/Sxx/` | Segmen audio milik satu penutur |
| `metadata/metadata.csv` | Satu baris per segmen: info penutur, rekaman, dan kualitas |
| `annotation/annotation.csv` | Satu baris per segmen: transkripsi, tag kejadian, Start/End, dan pemeriksa |
| `consent/consent_form/` | Formulir persetujuan (informed consent) penutur |
| `documentation/` | Dokumentasi korpus |

---

## Penamaan File

Pola: `S<ID penutur>_T<kode topik>_<nomor segmen>.wav`, contoh `S02_T01_001.wav`.

| Kode | Topik |
|---|---|
| T01 | Daily |
| T02 | Family |
| T03 | Food |
| T04 | Work_Education |
| T05 | Hobby |

---

## Penutur

| Speaker | Gender | Usia | Daerah | Status | Segmen | Durasi (menit) |
|---|---|---|---|---|---|---|
| S01 | M | 20 | Central Java | Non-native | 63 | 10,7 |
| S02 | F | 20 | Riau Islands | Non-native | 69 | 11,2 |
| S03 | M | 22 | West Java | Native | 88 | 14,4 |
| S04 | M | 20 | West Java | Native | 69 | 9,6 |
| S05 | M | 21 | West Java | Native | 66 | 10,2 |
| S06 | F | 21 | West Java | Native | 62 | 9,8 |
| S07 | F | 21 | West Java | Native | 63 | 11,8 |
| S08 | M | 17 | West Java | Native | 103 | 12,2 |
| S09 | F | 15 | West Java | Native | 61 | 8,8 |
| S10 | F | 51 | West Java | Native | 106 | 17,9 |
| **Total** | 5 M / 5 F | | | | **750** | **116,5** |

---

## Statistik

**Per topik**

| Topik | Segmen | Durasi (menit) |
|---|---|---|
| Daily | 156 | 25,2 |
| Family | 163 | 24,5 |
| Food | 137 | 21,7 |
| Work_Education | 136 | 21,4 |
| Hobby | 158 | 23,7 |

**Per gender**

| Gender | Penutur | Segmen | Durasi (menit) |
|---|---|---|---|
| Laki-laki (M) | 5 | 389 | 57,1 |
| Perempuan (F) | 5 | 361 | 59,4 |

**Per label kualitas**

| Label | Segmen | Durasi (menit) | Keterangan |
|---|---|---|---|
| Good | 679 | 103,5 | |
| Acceptable | 71 | 12,9 | S04 (5), S07 (63), S08 (3) |
| Reject | 0 | 0 | |

---

## Kolom `metadata.csv`

| Kolom | Isi |
|---|---|
| `File`, `Speaker` | Nama file WAV dan ID penutur (S01–S10) |
| `Age`, `Gender`, `Region` | Usia, gender (M/F), daerah asal |
| `Native_Status` | Native atau Non-native |
| `Language/Dialect` | Sunda |
| `Topic` | Daily, Family, Food, Work_Education, Hobby |
| `Duration` | Durasi segmen (detik) |
| `Environment` | Lingkungan rekaman |
| `Quality`, `Quality_Note` | Good / Acceptable / Reject beserta alasannya (`-` jika tidak ada catatan) |
| `Device`, `Recording_Date` | Perangkat dan tanggal rekam |
| `Channel`, `Bit_Depth`, `Sampling_Rate` | Mono, 16, 16000 |

## Kolom `annotation.csv`

| Kolom | Isi |
|---|---|
| `File`, `Speaker`, `Language/Dialect`, `Topic` | Sama dengan metadata |
| `Transcription` | Transkripsi ucapan, ditulis sesuai yang diucapkan |
| `Events` | Tag kejadian non-ucapan (`[noise]`, `[overlap]`), `-` jika tidak ada |
| `Start`, `End` | Awal dan akhir ucapan di dalam segmen (detik) |
| `Reviewed_By` | Anggota yang memeriksa segmen |

---

## Aturan Transkripsi

Teks ditulis sesuai ucapan penutur, termasuk kata serapan, tanpa membakukan ejaan. Kurung siku hanya dipakai untuk hal yang bukan kata.

| Jenis | Penulisan | Contoh |
|---|---|---|
| Filler (bunyi ragu) | `[ee]`, apa pun bunyinya | `abdi téh [ee] resep pisan` |
| Pengulangan | Apa adanya, tanpa kurung | `abdi, abdi téh` |
| Kata terpotong / ralat | Tanda hubung, tanpa kurung | `Sa- Saparua` |
| Kata seru *éh* | `éh` tanpa kurung, hanya jika bermakna | `Éh, kitu nya` |
| Noise sesaat | `[noise]` di posisi kejadian | `[noise] aduh Gusti` |
| Suara orang lain bersamaan | `[overlap]` di posisi kejadian | `... [overlap] kana bumbu kacang` |
| Bagian tidak jelas | `[unclear]` di posisi kejadian | `[unclear] Atmosférna téh alus pisan` |

- Untuk teks bersih tanpa filler dan tag, hapus semua yang berada di dalam `[...]`.
- Noise latar yang terdengar sepanjang segmen tidak ditandai di transkripsi, tetapi dicatat di `Quality_Note`.

---

## Kriteria Kualitas

| Label | Kriteria |
|---|---|
| Good | Ucapan jelas, tanpa clipping, noise latar sangat rendah, tidak ada suara lain, tidak terpotong, format benar |
| Acceptable | Ada noise atau gangguan ringan, tetapi ucapan tetap jelas dan dapat ditranskripsi |
| Reject | Clipping, noise mengganggu, suara orang lain dominan, ucapan terpotong, atau format tidak sesuai |

---

## Keterbatasan

- Usia penutur condong muda: 8 dari 10 penutur berusia 17–22 tahun.
- Seluruh segmen S07 direkam di kafe dan berisi noise latar (label Acceptable).
- S04, S06, dan S09 memiliki total durasi segmen sedikit di bawah 10 menit.
- S01 dan S02 adalah penutur non-native yang membacakan skrip.

## Etika dan Penggunaan

- Setiap penutur menandatangani formulir persetujuan sebelum direkam.
- Penutur diidentifikasi hanya dengan kode S01–S10 pada metadata, anotasi, dan nama file.
- Data hanya untuk keperluan akademik IF4071 dan tidak untuk tujuan komersial.

---

## Tim

| Nama | NIM |
|---|---|
| Nathaniel Jonathan Rusli | 13523013 |
| Maheswara Bayu Kaindra | 13523015 |
| Peter Wongsoredjo | 13523039 |
| Jessica Allen | 13523059 |
| Haegen Quinston | 13523109 |

IF4071 Pemrosesan Ucapan, Sekolah Teknik Elektro dan Informatika, Institut Teknologi Bandung, 2026.
