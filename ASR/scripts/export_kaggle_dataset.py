"""
Mengekspor folder dataset yang siap pakai di Kaggle.
Berisi audio dan CSV pembagian data .
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

ASR_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = ASR_ROOT.parent / "Korpus_Bahasa_Sunda"
SPLITS = ("train", "val", "test")
KEEP_COLS = ["file", "audio_path", "speaker_id", "transcription_original", "transcription_normalized",
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ASR_ROOT / "kaggle_export"))
    ap.add_argument("--corpus-root", default=str(CORPUS_ROOT))
    ap.add_argument("--splits", default=str(ASR_ROOT / "data" / "splits"))
    ap.add_argument("--slug", default="sundanese-asr-corpus", help="Slug dataset Kaggle")
    args = ap.parse_args()
    out, corpus, split_dir = Path(args.out), Path(args.corpus_root), Path(args.splits)
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} tidak kosong; hapus terlebih dahulu.")

    meta, parts = load_verified_split(split_dir)
    (out / "splits").mkdir(parents=True)
    n = 0
    for name, df in parts.items():
        df[KEEP_COLS].to_csv(out / "splits" / f"{name}.csv", index=False)
        for rel in df["audio_path"]:
            dst = out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(corpus / rel, dst)
            n += 1
    shutil.copy2(split_dir / "split_metadata.json", out / "splits" / "split_metadata.json")
    (out / "dataset-metadata.json").write_text(json.dumps(
        {"title": "Sundanese ASR Corpus", "id": f"<your-kaggle-username>/{args.slug}",
         "licenses": [{"name": "other"}]}, indent=2))
    print(f"{n} berkas wav diekspor, fingerprint {meta['manifest_fingerprint'][:12]} ke {out}")


if __name__ == "__main__":
    main()
