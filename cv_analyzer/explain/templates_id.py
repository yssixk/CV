"""Indonesian finding templates (menu 5a) — parallel to templates_en."""
from __future__ import annotations

TEMPLATES = {
    "vague_bullet": (
        "Poin di baris {line_number} berbunyi seperti tugas, bukan pencapaian "
        "(penanda: \"{cue}\"). Bukti: \"{evidence}\". Saran: {suggestion}"
    ),
    "redundant_pair": (
        "Baris {line_a} dan {line_b} menyampaikan hal yang sama (kemiripan {score:.2f}). "
        "Bukti A: \"{evidence_a}\" Bukti B: \"{evidence_b}\" Pertimbangkan menggabungkannya."
    ),
    "unsupported_claim": (
        "Klaim \"{claim}\" (baris {line_number}) tidak didukung bagian lain dalam CV. "
        "Saran: tambahkan contoh proyek atau angka yang membuktikannya."
    ),
    "missing_section": (
        "Bagian {section} tidak ditemukan. Bagian yang terdeteksi: {found_sections}. "
        "CV yang baik umumnya memuat ringkasan, pengalaman, pendidikan, dan keahlian."
    ),
    "very_short_bullet": (
        "Baris {line_number} terlalu singkat (\"{evidence}\"); perekrut tidak dapat mengetahui apa yang Anda kerjakan."
    ),
    "long_bullet": (
        "Baris {line_number} melebihi 40 kata; pecah agar setiap baris memuat satu poin."
    ),
    "generic_duty_summary": (
        "Ringkasan Anda memakai frasa umum (\"{evidence}\"); sesuaikan dengan posisi yang dituju."
    ),
}

SUGGESTIONS = {
    "vague_bullet": "tulis hasilnya: apa yang berubah, seberapa besar, untuk siapa.",
    "redundant_pair": "gabungkan kedua poin dan pertahankan yang lebih kuat.",
    "unsupported_claim": "dukung klaim dengan contoh konkret.",
}
