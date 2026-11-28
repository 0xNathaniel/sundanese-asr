"""Build the IF4071 collaboration draft with pdfLaTeX and BibTeX."""

from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


def compile_report(report_dir: Path) -> Path:
    executables = {name: shutil.which(name) for name in ("pdflatex", "bibtex")}
    missing = [name for name, executable in executables.items() if executable is None]
    if missing:
        raise RuntimeError(
            f"Alat TeX tidak ditemukan di PATH: {', '.join(missing)}. "
            "Pasang TeX Live atau MiKTeX untuk menjalankan kompilasi."
        )

    pdf_path = report_dir / "main.pdf"
    latex = [
        executables["pdflatex"],
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        "main.tex",
    ]
    bibtex = [executables["bibtex"], "main"]
    steps = (
        ("pdfLaTeX 1/3", latex),
        ("BibTeX", bibtex),
        ("pdfLaTeX 2/3", latex),
        ("pdfLaTeX 3/3", latex),
    )

    with TemporaryDirectory(prefix="latex-") as directory:
        stage = Path(directory)
        for filename in ("main.tex", "references.bib"):
            shutil.copy2(report_dir / filename, stage / filename)
        for folder in ("frontmatter", "chapters", "figures"):
            shutil.copytree(
                report_dir / folder,
                stage / folder,
                ignore=shutil.ignore_patterns("*.aux"),
            )

        for label, command in steps:
            print(f"Menjalankan {label}...", flush=True)
            result = subprocess.run(
                command,
                cwd=stage,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if result.returncode:
                print("\n".join(result.stdout.splitlines()[-20:]), file=sys.stderr)
                raise RuntimeError(f"{label} gagal (kode {result.returncode}).")

        built_pdf = stage / "main.pdf"
        if not built_pdf.is_file():
            raise RuntimeError("PDF tidak terbentuk.")
        shutil.copy2(built_pdf, pdf_path)

    return pdf_path


def main() -> int:
    try:
        pdf_path = compile_report(Path(__file__).resolve().parent)
    except (OSError, RuntimeError) as error:
        print(f"Kompilasi gagal. {error}", file=sys.stderr)
        return 1
    print(f"PDF tersedia di {pdf_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
