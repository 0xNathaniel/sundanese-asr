"""
Mengekspor folder dataset yang siap pakai di Kaggle.
Berisi audio dan CSV pembagian data dari korpus kami dan korpus G04.
Audio yang bukan 16 kHz diturunkan ke 16 kHz agar semua berkas siap dipakai wav2vec 2.0.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf
from scipy.signal import resample_poly

ASR_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ASR_ROOT.parent
TARGET_SR = 16000
SPLITS = ("train", "val", "test")
KEEP_COLS = ["file", "source_corpus", "audio_path", "speaker_id", "transcription_original", "transcription_normalized",
             "needs_review", "duration", "quality", "native_status", "topic", "split"]


def load_verified_split(split_dir: Path):
    """Memastikan CSV tersimpan konsisten dengan metadata dan tidak ada penutur maupun ujaran yang overlapping."""
    meta = json.loads((split_dir / "split_metadata.json").read_text())
    parts = {name: pd.read_csv(split_dir / f"{name}.csv") for name in SPLITS}
    for name, df in parts.items():
        if set(df["speaker_id"]) != set(meta["subsets"][name]["speakers"]):
            raise AssertionError(f"Penutur {name}.csv berbeda dari split_metadata.json")
    for i, a in enumerate(SPLITS):
        for b in SPLITS[i + 1:]:
            if not set(parts[a]["speaker_id"]).isdisjoint(parts[b]["speaker_id"]):
                raise AssertionError(f"Penutur tumpang tindih antara {a} dan {b}")
            if not set(parts[a]["file"]).isdisjoint(parts[b]["file"]):
                raise AssertionError(f"Ujaran tumpang tindih antara {a} dan {b}")
    return meta, parts


def export_audio(src: Path, dst: Path) -> bool:
    """Menyalin audio 16 kHz apa adanya dan menurunkan laju sampel lainnya. Mengembalikan True bila diresample."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    sr = sf.info(str(src)).samplerate
    if sr == TARGET_SR:
        shutil.copy2(src, dst)
        return False
    wav, _ = sf.read(str(src), dtype="float32")
    gcd = np.gcd(sr, TARGET_SR)
    # resample_poly memakai filter anti-aliasing sehingga frekuensi di atas 8 kHz tidak terlipat ke rentang suara.
    out = resample_poly(wav, TARGET_SR // gcd, sr // gcd).astype(np.float32)
    sf.write(str(dst), np.clip(out, -1.0, 1.0), TARGET_SR, subtype="PCM_16")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ASR_ROOT / "kaggle_export"))
    ap.add_argument("--repo-root", default=str(REPO_ROOT))
    ap.add_argument("--splits", default=str(ASR_ROOT / "data" / "splits"))
    ap.add_argument("--slug", default="sundanese-asr-corpus", help="Slug dataset Kaggle")
    args = ap.parse_args()
    out, repo, split_dir = Path(args.out), Path(args.repo_root), Path(args.splits)
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} tidak kosong; hapus terlebih dahulu.")

    meta, parts = load_verified_split(split_dir)
    (out / "splits").mkdir(parents=True)
    n = n_resampled = 0
    for name, df in parts.items():
        df[KEEP_COLS].to_csv(out / "splits" / f"{name}.csv", index=False)
        for src, rel in zip(df["source_path"], df["audio_path"]):
            n_resampled += export_audio(repo / src, out / rel)
            n += 1
    shutil.copy2(split_dir / "split_metadata.json", out / "splits" / "split_metadata.json")
    (out / "dataset-metadata.json").write_text(json.dumps(
        {"title": "Sundanese ASR Corpus", "id": f"<your-kaggle-username>/{args.slug}",
         "licenses": [{"name": "other"}]}, indent=2))
    print(f"{n} berkas wav diekspor, {n_resampled} diresample ke {TARGET_SR} Hz, fingerprint {meta['manifest_fingerprint'][:12]} ke {out}")


if __name__ == "__main__":
    main()
