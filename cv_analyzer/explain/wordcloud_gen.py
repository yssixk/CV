"""Wordcloud generation (luaran makalah): frekuensi kata dari hasil analisis CV.

Dua mode, keduanya hitam-putih (kebutuhan format jurnal: tidak boleh ada
warna) dan deterministik (seed tetap -> gambar identik antar-run, penting
untuk reproduksibilitas makalah):

1. ``generate_skill_cloud``  — dari gabungan teks CV (bobot = frekuensi kata
   konten; alias skill dipetakan ke nama kanonis sehingga "js" dan
   "JavaScript" terhitung satu konsep).
2. ``generate_finding_cloud`` — dari pesan temuan (kind + kata kunci pesan),
   memperlihatkan tema keluhan yang paling sering muncul pada korpus.

Stopwords EN + ID dibangun dari wordlist yang sama dengan modul lang_id agar
konsisten dengan pipeline. Output: file PNG (matplotlib, dpi 200).
"""
from __future__ import annotations

import re
from pathlib import Path

from cv_analyzer.models import Finding
from cv_analyzer.utils.gazetteer_loader import load_gazetteer

WORD_RE = re.compile(r"[a-z0-9+#]+")

# Stopwords gabungan (EN + ID) — subset yang sama dengan lang_id + tambahan
# kata umum CV agar awan kata memunculkan konten, bukan fungsi tata bahasa.
STOPWORDS: set[str] = {
    # English
    "the", "a", "an", "and", "or", "but", "with", "for", "from", "in", "on", "at",
    "to", "of", "by", "as", "is", "are", "was", "were", "be", "been", "this",
    "that", "these", "those", "it", "its", "their", "our", "my", "which", "while",
    "during", "after", "before", "about", "into", "over", "under", "than", "then",
    "also", "your", "you", "we", "line", "lines", "bullet", "consider",
    # Indonesian
    "dan", "atau", "tetapi", "dengan", "untuk", "dari", "di", "ke", "pada",
    "dalam", "adalah", "ialah", "yaitu", "yang", "ini", "itu", "saya", "kami",
    "kita", "anda", "oleh", "sebagai", "kepada", "akan", "telah", "sedang",
    "tidak", "bisa", "dapat", "agar", "serta", "selama", "setelah", "sebelum",
    "hingga", "sampai", "antara", "semua", "setiap", "juga", "masih", "sudah",
    "belum", "ada", "baris", "pertimbangkan", "buat", "bukti", "saran",
}


def _canonical_map() -> dict[str, str]:
    """Alias -> nama kanonis (dari kedua gazetteer), untuk penggabungan konsep."""
    lookup: dict[str, str] = {}
    for canonical, spec in load_gazetteer("skills_en").items():
        for alias in spec.get("aliases", []):
            lookup[alias.lower()] = canonical.lower()
        lookup[canonical.lower()] = canonical.lower()
    for canonical, aliases in load_gazetteer("skills_id").items():
        for alias in aliases:
            lookup[alias.lower()] = canonical.lower()
    return lookup


_CANONICAL_LOOKUP = _canonical_map()


def _content_words(text: str, merge_skill_aliases: bool = True) -> list[str]:
    """Kata konten: buang stopwords, petakan alias ke kanonis, lalu saring pendek.

    Urutan penting: alias pendek yang dikenal ("js", "r", "k8s") harus dipetakan
    SEBELUM filter panjang, agar konsep skill tidak hilang; token pendek tak
    dikenal (noise) tetap dibuang.
    """
    out: list[str] = []
    for token in WORD_RE.findall(text.lower()):
        if token in STOPWORDS:
            continue
        canonical = _CANONICAL_LOOKUP.get(token, token) if merge_skill_aliases else token
        is_known_skill = token in _CANONICAL_LOOKUP
        if len(canonical) <= 2 and not is_known_skill:
            continue
        out.append(canonical)
    return out


def word_frequencies(texts: list[str], merge_skill_aliases: bool = True) -> dict[str, int]:
    """Hitung frekuensi kata konten dari kumpulan teks."""
    from collections import Counter

    counter: Counter[str] = Counter()
    for text in texts:
        counter.update(_content_words(text, merge_skill_aliases))
    return dict(counter)


def _render_cloud(
    frequencies: dict[str, int],
    out_path: Path,
    width: int = 1600,
    height: int = 800,
    title: str = "",
) -> Path:
    """Render wordcloud hitam-putih ke PNG via matplotlib. Deterministik."""
    if not frequencies:
        raise ValueError("wordcloud butuh minimal satu kata")
    from wordcloud import WordCloud
    import matplotlib
    matplotlib.use("Agg")  # headless: tidak butuh display, aman di server
    import matplotlib.pyplot as plt

    wc = WordCloud(
        width=width,
        height=height,
        background_color="white",
        colormap="Greys",          # grayscale — sesuai ketentuan jurnal tanpa warna
        prefer_horizontal=1.0,
        random_state=42,           # deterministik
        min_font_size=10,
        max_words=80,
    )
    wc.generate_from_frequencies(frequencies)

    fig, ax = plt.subplots(figsize=(width / 200, height / 200), dpi=200)
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    if title:
        ax.set_title(title, fontsize=10, color="black")
    fig.tight_layout(pad=0.5)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def generate_skill_cloud(cv_texts: list[str], out_path: str | Path) -> Path:
    """Awan kata dari isi CV (skill & istilah teknis paling sering)."""
    freq = word_frequencies(cv_texts, merge_skill_aliases=True)
    return _render_cloud(freq, Path(out_path), title="Wordcloud isi CV")


def generate_finding_cloud(findings: list[Finding], out_path: str | Path) -> Path:
    """Awan kata dari pesan temuan sistem (tema keluhan paling sering)."""
    freq = word_frequencies([f.message for f in findings], merge_skill_aliases=False)
    return _render_cloud(freq, Path(out_path), title="Wordcloud temuan analisis")
