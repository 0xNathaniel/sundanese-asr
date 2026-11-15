"""
Menyiapkan korpus bahasa Sunda untuk eksperimen ASR.
Berkas korpus sumber hanya dibaca dan tidak pernah diubah.

Tahapan yang dilakukan:
1. Menggabungkan anotasi dan metadata berdasarkan nama berkas audio.
2. Memvalidasi audio dan transkripsi setiap ujaran.
3. Menormalisasi transkripsi dengan kebijakan yang sama untuk kedua model.
4. Membagi penutur secara acak dengan seed 42 menjadi 6 train, 2 val, dan 2 test.
5. Menyimpan manifes, CSV pembagian data, dan metadata pembagian.

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
CORPUS_ROOT = ASR_ROOT.parent / "Korpus_Bahasa_Sunda"
SEED = 42
SIZES = {"train": 6, "val": 2, "test": 2}
ALGORITHM = ("sorted unique speaker ids -> numpy.random.RandomState(seed).permutation "
             "-> first 6 train, next 2 val, last 2 test")

NORMALIZATION_VERSION = "v1"
ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyzé ")
REMOVED_TAGS = {"ee", "ee..", "noise", "overlap", "s"}
REVIEW_TAGS = {"unclear"}
DIGITS = {"0": "nol", "1": "hiji", "2": "dua", "3": "tilu", "4": "opat",
          "5": "lima", "6": "genep", "7": "tujuh", "8": "dalapan", "9": "salapan"}
# Satu-satunya token gabungan huruf dan angka di korpus sehingga bentuk lisannya ditetapkan secara eksplisit.
SPOKEN_FORMS = {"s2": "es dua"}
TAG_RE = re.compile(r"\[([^\]]*)\]")
NUMBER_RE = re.compile(r"(?<![^\W\d_])\d+(?![^\W\d_])")

MANIFEST_COLUMNS = ["file", "audio_path", "speaker_id", "transcription_original", "transcription_normalized",
                    "needs_review", "duration", "quality", "native_status", "topic", "split"]
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


def build_manifest(corpus_root: Path):
    """Menggabungkan anotasi dan metadata berdasarkan File, menormalisasi teks, lalu memvalidasi."""
    ann = pd.read_csv(corpus_root / "annotation" / "annotation.csv")
    meta = pd.read_csv(corpus_root / "metadata" / "metadata.csv")
    for name, df in (("annotation", ann), ("metadata", meta)):
        if not df["File"].is_unique:
            raise ValueError(f"{name}: nama berkas audio duplikat: {df['File'][df['File'].duplicated()].tolist()}")
    if set(ann["File"]) != set(meta["File"]):
        raise ValueError(f"File anotasi dan metadata tidak cocok: hanya-anotasi={sorted(set(ann['File']) - set(meta['File']))[:5]} "
                         f"hanya-metadata={sorted(set(meta['File']) - set(ann['File']))[:5]}")
    df = ann.merge(meta, on="File", suffixes=("_ann", "_meta"), validate="one_to_one")
    if (df["Speaker_ann"] != df["Speaker_meta"]).any():
        raise ValueError("Penutur berbeda antara anotasi dan metadata untuk: "
                         f"{df.loc[df['Speaker_ann'] != df['Speaker_meta'], 'File'].tolist()[:5]}")

    rows, excluded = [], []
    for r in df.itertuples():
        reasons = []
        if r.Quality not in ELIGIBLE_QUALITY:
            reasons.append(f"kualitas={r.Quality}")
        if not isinstance(r.Transcription, str) or not r.Transcription.strip():
            reasons.append("transkripsi kosong")
        if not str(r.Speaker_ann).startswith("S"):
            reasons.append("ID penutur tidak valid")
        rel = f"audio/{r.Speaker_ann}/{r.File}"
        text, needs_review = "", False
        if not reasons:
            text, needs_review = normalize_transcript(r.Transcription)
            if not text:
                reasons.append("kosong setelah normalisasi")
            path = corpus_root / rel
            if not path.exists():
                reasons.append("berkas audio tidak ada")
            else:
                info = sf.info(str(path))
                if info.frames == 0:
                    reasons.append("audio kosong")
                elif info.samplerate != 16000 or info.channels != 1 or info.subtype != "PCM_16":
                    reasons.append(f"format salah sr={info.samplerate} ch={info.channels} {info.subtype}")
                elif abs(info.frames / info.samplerate - float(r.Duration)) > 0.2:
                    reasons.append(f"durasi tidak cocok metadata={r.Duration} aktual={info.frames / info.samplerate:.2f}")
        if reasons:
            excluded.append({"file": r.File, "reasons": "; ".join(reasons)})
            continue
        rows.append({
            "file": r.File, "audio_path": rel, "speaker_id": r.Speaker_ann,
            "transcription_original": r.Transcription, "transcription_normalized": text,
            "needs_review": needs_review, "duration": float(r.Duration),
            "quality": r.Quality, "native_status": NATIVE_FIX.get(r.Native_Status, r.Native_Status),
            "topic": r.Topic_ann, "split": "",
        })
    manifest = pd.DataFrame(rows, columns=MANIFEST_COLUMNS).sort_values("file").reset_index(drop=True)
    return manifest, excluded


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
        "utterances_per_speaker": {k: int(v) for k, v in df["speaker_id"].value_counts().sort_index().items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-root", default=str(CORPUS_ROOT))
    ap.add_argument("--out-dir", default=str(ASR_ROOT / "data"))
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    out = Path(args.out_dir)
    split_dir = out / "splits"
    meta_path = split_dir / "split_metadata.json"

    manifest, excluded = build_manifest(Path(args.corpus_root))
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
        "excluded_files": excluded,
        "needs_review_files": manifest.loc[manifest["needs_review"], "file"].tolist(),
        "note": "Random speaker-level split; no balancing by gender/native status/noise was applied.",
    }
    split_dir.mkdir(parents=True, exist_ok=True)
    for name, df in parts.items():
        df.to_csv(split_dir / f"{name}.csv", index=False)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    manifest.to_csv(out / "manifest.csv", index=False)
    print(json.dumps({k: v for k, v in meta.items() if k != "excluded_files"}, indent=2, ensure_ascii=False))
    print(f"dikecualikan: {len(excluded)}")


if __name__ == "__main__":
    main()
