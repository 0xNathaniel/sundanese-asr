"""
Menyiapkan korpus bahasa Sunda kelompok kami dan kelompok G04 untuk eksperimen ASR.
Berkas korpus sumber hanya dibaca dan tidak pernah diubah.

Tahapan yang dilakukan:
1. Menggabungkan anotasi dan metadata setiap korpus berdasarkan nama berkas audio.
2. Memperbaiki nama berkas anotasi G04 yang kode topiknya tidak cocok dengan metadata.
3. Memberi awalan G04 pada ID penutur dan nama berkas G04 agar tidak bentrok.
4. Memvalidasi audio dan transkripsi setiap ujaran.
5. Menormalisasi transkripsi dengan kebijakan yang sama untuk semua korpus dan kedua model.
6. Membagi penutur secara acak dengan seed 42 menjadi 13 train, 4 val, dan 4 test.
7. Menyimpan manifes, CSV pembagian data, dan metadata pembagian.

Aturan normalisasi:
1. Teks diubah ke bentuk NFC dan huruf kecil.
2. Tag ee, noise, overlap, dan s dihapus.
3. Tag unclear dihapus dan ujarannya ditandai untuk ditinjau.
4. Tag lain dibuka dan katanya dipertahankan.
5. Angka 0 sampai 99 dieja dalam bahasa Sunda.
6. Tanda hubung menjadi spasi dan tanda baca lain dihapus.
7. Huruf e-acute dipertahankan.
"""
import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf

ASR_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ASR_ROOT.parent
MAIN_CORPUS = "Korpus_Bahasa_Sunda"
G04_CORPUS = "Korpus_Bahasa_Sunda_G04"
SEED = 42
SIZES = {"train": 13, "val": 4, "test": 4}
ALGORITHM = ("sorted unique speaker ids -> numpy.random.RandomState(seed).permutation "
             "-> first 13 train, next 4 val, last 4 test")
# Audio 48 kHz diterima di sini dan diturunkan ke 16 kHz saat ekspor.
ALLOWED_SAMPLE_RATES = {16000, 48000}
# wav2vec 2.0 menghasilkan satu frame setiap 20 ms.
FRAMES_PER_SECOND = 50

NORMALIZATION_VERSION = "v1"
ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyzé ")
REMOVED_TAGS = {"ee", "ee..", "noise", "overlap", "s"}
REVIEW_TAGS = {"unclear"}
DIGITS = {"0": "nol", "1": "hiji", "2": "dua", "3": "tilu", "4": "opat",
          "5": "lima", "6": "genep", "7": "tujuh", "8": "dalapan", "9": "salapan"}
# Token yang tidak tercakup aturan angka 0 sampai 99 sehingga bentuk lisannya ditetapkan secara eksplisit.
SPOKEN_FORMS = {"s2": "es dua", "2023": "dua rebu dua puluh tilu"}
TAG_RE = re.compile(r"\[([^\]]*)\]")
NUMBER_RE = re.compile(r"(?<![^\W\d_])\d+(?![^\W\d_])")

MANIFEST_COLUMNS = ["file", "source_corpus", "source_path", "audio_path", "speaker_id", "transcription_original",
                    "transcription_normalized", "needs_review", "duration", "sample_rate", "quality",
                    "native_status", "topic", "split"]
ELIGIBLE_QUALITY = {"Good", "Acceptable"}
# Memperbaiki salah ketik pada metadata hanya di manifes tanpa mengubah berkas sumber
NATIVE_FIX = {"Non--native": "Non-native"}


def spell_number(num: str) -> str:
    if len(num) > 2 or (len(num) > 1 and num.startswith("0")):
        raise ValueError(f"Angka {num!r} di luar pemetaan eksplisit 0-99.")
    n = int(num)
    if n < 10:
        return DIGITS[num]
    tens, unit = divmod(n, 10)
    if n == 10:
        return "sapuluh"
    if n == 11:
        return "sabelas"
    if tens == 1:
        return f"{DIGITS[str(unit)]} welas"
    return f"{DIGITS[str(tens)]} puluh" + (f" {DIGITS[str(unit)]}" if unit else "")


def normalize_transcript(raw: str):
    """Mengembalikan teks ternormalisasi dan penanda apakah ujaran perlu ditinjau."""
    needs_review = False
    text = unicodedata.normalize("NFC", raw).lower()

    def handle_tag(m):
        nonlocal needs_review
        inner = " ".join(m.group(1).split())
        if inner in REMOVED_TAGS:
            return " "
        if inner in REVIEW_TAGS:
            needs_review = True
            return " "
        return f" {inner} "

    text = TAG_RE.sub(handle_tag, text)
    for written, spoken in SPOKEN_FORMS.items():
        text = re.sub(rf"\b{re.escape(written)}\b", spoken, text)
    text = NUMBER_RE.sub(lambda m: f" {spell_number(m.group(0))} ", text)
    if re.search(r"\d", text):
        raise ValueError(f"Angka yang menempel pada huruf tidak didukung: {raw!r}")
    text = re.sub(r"[-‐-―]", " ", text)
    text = "".join(ch if (ch.isalpha() or ch.isspace()) else " " for ch in text)
    text = " ".join(text.split())
    bad = sorted(set(text) - ALLOWED_CHARS)
    if bad:
        raise ValueError(f"Karakter tidak didukung {bad} setelah normalisasi: {raw!r}")
    return text, needs_review


def audio_problem(path: Path):
    """Mengembalikan alasan penolakan audio, atau None bila audio layak dipakai."""
    if not path.exists():
        return "berkas audio tidak ada"
    info = sf.info(str(path))
    if info.frames == 0:
        return "audio kosong"
    if info.samplerate not in ALLOWED_SAMPLE_RATES or info.channels != 1 or info.subtype != "PCM_16":
        return f"format salah sr={info.samplerate} ch={info.channels} {info.subtype}"
    return None


def ctc_feasible(text: str, duration: float) -> bool:
    """CTC hanya dapat memetakan audio ke label bila jumlah frame cukup untuk seluruh karakter dan blank pemisah huruf kembar."""
    repeats = sum(1 for x, y in zip(text, text[1:]) if x == y)
    return len(text) + repeats <= int(duration * FRAMES_PER_SECOND)


def make_rows(records, repo_root: Path):
    """Memvalidasi dan menormalisasi ujaran dari semua korpus dengan aturan yang sama.

    Durasi diambil dari audio karena durasi di metadata G04 S05 tertukar antar baris.
    Selisih dengan metadata dicatat tetapi tidak membuat ujaran dikecualikan.
    """
    rows, excluded, duration_mismatches = [], [], []
    for r in records:
        reasons = []
        if r["quality"] not in ELIGIBLE_QUALITY:
            reasons.append(f"kualitas={r['quality']}")
        raw = r["transcription_original"]
        if not isinstance(raw, str) or not raw.strip():
            reasons.append("transkripsi kosong")
        text, needs_review, sample_rate = "", False, None
        if not reasons:
            text, needs_review = normalize_transcript(raw)
            if not text:
                reasons.append("kosong setelah normalisasi")
            problem = audio_problem(repo_root / r["source_path"])
            if problem:
                reasons.append(problem)
            else:
                info = sf.info(str(repo_root / r["source_path"]))
                sample_rate = info.samplerate
                actual = round(info.frames / info.samplerate, 4)
                if abs(actual - r["duration"]) > 0.2:
                    duration_mismatches.append({"file": r["file"], "metadata": r["duration"], "audio": actual})
                r = {**r, "duration": actual}
                if text and not ctc_feasible(text, actual):
                    reasons.append("transkripsi terlalu panjang untuk durasi audio")
        if reasons:
            excluded.append({"file": r["file"], "source_corpus": r["source_corpus"], "reasons": "; ".join(reasons)})
            continue
        rows.append({**r, "transcription_normalized": text, "needs_review": needs_review,
                     "sample_rate": sample_rate, "split": ""})
    return rows, excluded, duration_mismatches


def check_join(ann: pd.DataFrame, meta: pd.DataFrame, corpus: str) -> None:
    for name, df in (("anotasi", ann), ("metadata", meta)):
        if not df["File"].is_unique:
            raise ValueError(f"{corpus} {name}: nama berkas audio duplikat: {df['File'][df['File'].duplicated()].tolist()[:5]}")
    if set(ann["File"]) != set(meta["File"]):
        raise ValueError(f"{corpus}: File anotasi dan metadata tidak cocok: "
                         f"hanya-anotasi={sorted(set(ann['File']) - set(meta['File']))[:5]} "
                         f"hanya-metadata={sorted(set(meta['File']) - set(ann['File']))[:5]}")


def load_main_corpus(repo_root: Path):
    """Korpus kelompok kami. ID penutur dan path audio tetap sama seperti pembagian sebelumnya."""
    root = repo_root / MAIN_CORPUS
    ann = pd.read_csv(root / "annotation" / "annotation.csv")
    meta = pd.read_csv(root / "metadata" / "metadata.csv")
    check_join(ann, meta, MAIN_CORPUS)
    df = ann.merge(meta, on="File", suffixes=("_ann", "_meta"), validate="one_to_one")
    if (df["Speaker_ann"] != df["Speaker_meta"]).any():
        raise ValueError(f"{MAIN_CORPUS}: penutur berbeda antara anotasi dan metadata untuk "
                         f"{df.loc[df['Speaker_ann'] != df['Speaker_meta'], 'File'].tolist()[:5]}")
    return [{
        "file": r.File, "source_corpus": MAIN_CORPUS, "source_path": f"{MAIN_CORPUS}/audio/{r.Speaker_ann}/{r.File}",
        "audio_path": f"audio/{r.Speaker_ann}/{r.File}", "speaker_id": r.Speaker_ann,
        "transcription_original": r.Transcription, "duration": float(r.Duration), "quality": r.Quality,
        "native_status": NATIVE_FIX.get(r.Native_Status, r.Native_Status), "topic": r.Topic_ann,
    } for r in df.itertuples()], []


def g04_speaker(file_name: str) -> str:
    return file_name.split("_")[0].upper()


def load_g04_corpus(repo_root: Path):
    """Korpus kelompok G04 yang terpecah per penutur dan memakai skema kolom berbeda.

    ID penutur dan nama berkas diberi awalan G04 karena bentrok dengan ID korpus kami.
    """
    root = repo_root / G04_CORPUS
    ann = pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in sorted((root / "annotation").glob("*.csv"))],
                    ignore_index=True).rename(columns={"Label Speaker": "AnnSpeaker"})
    meta = pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in sorted((root / "metadata").glob("*.csv"))],
                     ignore_index=True)

    # Sebagian nama berkas di anotasi memakai kode topik yang salah, sedangkan metadata dan audio benar.
    # Pasangan dicocokkan lewat penutur dan nomor ujaran yang unik per penutur.
    meta_names = set(meta["File"])
    by_number = {}
    for f in meta_names:
        by_number.setdefault((g04_speaker(f), f.split("_")[2]), []).append(f)
    name_fixes = []
    for i, f in ann["File"].items():
        if f not in meta_names:
            candidates = by_number.get((g04_speaker(f), f.split("_")[2]), [])
            if len(candidates) != 1:
                raise ValueError(f"{G04_CORPUS}: {f} tidak dapat dipasangkan dengan metadata, kandidat {candidates}")
            ann.at[i, "File"] = candidates[0]
            name_fixes.append({"annotation_file": f, "metadata_file": candidates[0]})
    check_join(ann, meta, G04_CORPUS)

    df = ann.merge(meta, on="File", validate="one_to_one")
    audio_index = {p.name: p for p in (root / "audio").rglob("*") if p.suffix.lower() == ".wav"}
    records = []
    for r in df.itertuples():
        speaker = g04_speaker(r.File)
        meta_speaker = str(r.Speaker)
        meta_speaker = f"S{int(meta_speaker):02d}" if meta_speaker.isdigit() else meta_speaker.upper()
        if speaker != str(r.AnnSpeaker).upper() or speaker != meta_speaker:
            raise ValueError(f"{G04_CORPUS}: penutur tidak konsisten untuk {r.File}: "
                             f"anotasi={r.AnnSpeaker} metadata={r.Speaker}")
        source = audio_index.get(r.File)
        stem = Path(r.File).stem
        records.append({
            "file": f"G04_{r.File}", "source_corpus": G04_CORPUS,
            "source_path": str(source.relative_to(repo_root)) if source else f"{G04_CORPUS}/audio/{r.File}",
            "audio_path": f"audio/G04/{speaker}/{stem}.wav", "speaker_id": f"G04_{speaker}",
            "transcription_original": r.Transkripsi, "duration": float(r.Duration),
            "quality": str(r.Quality).strip().capitalize(), "native_status": "Unknown", "topic": r.Topic,
        })
    return records, name_fixes


def build_manifest(repo_root: Path):
    main_records, _ = load_main_corpus(repo_root)
    g04_records, name_fixes = load_g04_corpus(repo_root)
    rows, excluded, duration_mismatches = make_rows(main_records + g04_records, repo_root)
    manifest = pd.DataFrame(rows, columns=MANIFEST_COLUMNS).sort_values("file").reset_index(drop=True)
    if not manifest["file"].is_unique or not manifest["audio_path"].is_unique:
        raise ValueError("Nama berkas atau path audio tidak unik setelah penggabungan korpus")
    return manifest, excluded, {"g04_annotation_name_fixes": name_fixes, "metadata_duration_mismatches": duration_mismatches}


def fingerprint(manifest: pd.DataFrame) -> str:
    h = hashlib.sha256(NORMALIZATION_VERSION.encode())
    for r in manifest.sort_values("file").itertuples():
        h.update(f"{r.file}|{r.speaker_id}|{r.transcription_normalized}|{r.quality}|{r.duration}\n".encode())
    return h.hexdigest()


def assign_speakers(speakers, seed: int) -> dict:
    spk = sorted(set(speakers))
    if len(spk) != sum(SIZES.values()):
        raise ValueError(f"Dibutuhkan {sum(SIZES.values())} penutur, ditemukan {len(spk)}: {spk}")
    shuffled = [spk[i] for i in np.random.RandomState(seed).permutation(len(spk))]
    out, start = {}, 0
    for name in ("train", "val", "test"):
        out[name] = sorted(shuffled[start:start + SIZES[name]])
        start += SIZES[name]
    sets = {k: set(v) for k, v in out.items()}
    assert sets["train"].isdisjoint(sets["val"])
    assert sets["train"].isdisjoint(sets["test"])
    assert sets["val"].isdisjoint(sets["test"])
    return out


def subset_summary(df: pd.DataFrame, speakers: list) -> dict:
    return {
        "speakers": speakers,
        "n_utterances": int(len(df)),
        "total_duration_sec": round(float(df["duration"].sum()), 2),
        "quality_counts": {k: int(v) for k, v in df["quality"].value_counts().items()},
        "native_status_counts": {k: int(v) for k, v in df["native_status"].value_counts().items()},
        "source_corpus_counts": {k: int(v) for k, v in df["source_corpus"].value_counts().items()},
        "utterances_per_speaker": {k: int(v) for k, v in df["speaker_id"].value_counts().sort_index().items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=str(REPO_ROOT))
    ap.add_argument("--out-dir", default=str(ASR_ROOT / "data"))
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    out = Path(args.out_dir)
    split_dir = out / "splits"
    meta_path = split_dir / "split_metadata.json"

    manifest, excluded, data_fixes = build_manifest(Path(args.repo_root))
    fp = fingerprint(manifest)
    if meta_path.exists() and not args.force:
        changed = json.loads(meta_path.read_text()).get("manifest_fingerprint") != fp
        raise FileExistsError(
            f"Pembagian sudah ada di {split_dir}; tidak ditimpa diam-diam. "
            + ("Fingerprint manifes BERUBAH: jalankan ulang dengan --force secara sengaja." if changed
               else "Gunakan --force hanya bila memang ingin menimpa."))

    assign = assign_speakers(manifest["speaker_id"], args.seed)
    lookup = {s: part for part, speakers in assign.items() for s in speakers}
    manifest["split"] = manifest["speaker_id"].map(lookup)
    parts = {name: manifest[manifest["split"] == name].reset_index(drop=True) for name in SIZES}
    if sum(len(p) for p in parts.values()) != len(manifest):
        raise AssertionError("Setiap ujaran harus tepat berada di satu partisi")

    meta = {
        "seed": args.seed, "algorithm": ALGORITHM, "manifest_fingerprint": fp, "target_sizes": SIZES,
        "subsets": {name: subset_summary(df, assign[name]) for name, df in parts.items()},
        "normalization_version": NORMALIZATION_VERSION,
        "n_eligible": int(len(manifest)),
        "source_corpus_counts": {k: int(v) for k, v in manifest["source_corpus"].value_counts().items()},
        "excluded_files": excluded,
        **data_fixes,
        "needs_review_files": manifest.loc[manifest["needs_review"], "file"].tolist(),
        "note": "Random speaker-level split; no balancing by gender/native status/noise was applied.",
    }
    split_dir.mkdir(parents=True, exist_ok=True)
    for name, df in parts.items():
        df.to_csv(split_dir / f"{name}.csv", index=False)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    manifest.to_csv(out / "manifest.csv", index=False)
    print(json.dumps({k: v for k, v in meta.items() if k not in ("excluded_files", *data_fixes)}, indent=2, ensure_ascii=False))
    print(f"dikecualikan: {len(excluded)} | " + " | ".join(f"{k}: {len(v)}" for k, v in data_fixes.items()))


if __name__ == "__main__":
    main()
