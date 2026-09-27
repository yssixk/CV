"""Language identification tests — accuracy measured on a hand-labeled 50-bullet set.

Per the build brief (Phase 3 acceptance): report accuracy empirically, do not
assume either detector is good enough. The labeled set below is realistic
mixed EN/ID CV bullet material.
"""
from __future__ import annotations

import pytest

from cv_analyzer.understand.lang_id import classify_language, wordlist_classify

# --- hand-labeled bullets (label = expected language) ----------------------

EN_BULLETS = [
    "Reduced report generation time by 40% by automating the pipeline with Python.",
    "Responsible for various reports and dashboards for the sales team.",
    "Built an automated Excel workbook that cut manual consolidation from 6 hours to 30 minutes.",
    "Led a team of four junior analysts across three projects.",
    "Assisted with data cleaning and monthly reconciliation tasks.",
    "Presented quarterly findings to senior stakeholders.",
    "Designed and implemented a REST API for the inventory system.",
    "Worked on monthly sales data and ad-hoc requests.",
    "Improved test coverage from 45% to 80% across the codebase.",
    "Coordinated with the marketing team on campaign analytics.",
    "Managed the migration of legacy data to PostgreSQL.",
    "Helped new team members onboard and understand the codebase.",
    "Achieved the highest customer satisfaction score in the region.",
    "Trained three interns on the company data tooling.",
    "Automated invoice processing, saving 20 hours per week.",
    "Collaborated with designers to ship the new dashboard.",
    "Analyzed churn drivers and recommended retention actions.",
    "Handled customer complaints and escalations.",
    "Wrote technical documentation for the analytics platform.",
    "Mentored two associates who were promoted within a year.",
    "Optimized slow SQL queries, cutting page load times in half.",
    "Supported the finance team during quarterly audits.",
    "Developed a forecasting model that improved accuracy by 12%.",
    "Participated in code reviews and sprint planning.",
    "Owned the data quality process for the CRM pipeline.",
]

ID_BULLETS = [
    "Mengembangkan fitur checkout baru menggunakan React dan TypeScript.",
    "Bertanggung jawab atas laporan penjualan bulanan untuk tim marketing.",
    "Membangun aplikasi mobile untuk layanan pelanggan internal.",
    "Memimpin tim beranggotakan lima orang dalam proyek migrasi data.",
    "Membantu proses rekrutmen dan onboarding karyawan baru.",
    "Menganalisis data pelanggan untuk menyusun strategi promosi.",
    "Menangani keluhan pelanggan melalui telepon dan email.",
    "Berpartisipasi dalam rapat mingguan bersama tim produk.",
    "Mengurangi waktu pemrosesan laporan sebesar 30 persen.",
    "Menyusun dokumentasi teknis untuk sistem informasi akademik.",
    "Mengelola media sosial perusahaan dan meningkatkan pengikut sebesar 50%.",
    "Bekerja sama dengan tim desain untuk meluncurkan fitur baru.",
    "Melakukan pengujian aplikasi sebelum rilis ke pengguna.",
    "Membuat dashboard pemantauan penjualan secara real time.",
    "Mengikuti pelatihan pengembangan web selama tiga bulan.",
    "Menulis artikel teknis untuk blog perusahaan.",
    "Mengoptimalkan query database sehingga aplikasi lebih cepat.",
    "Memberikan pelatihan komputer kepada staf administrasi.",
    "Mengarahkan mahasiswa magang dalam menyelesaikan proyek.",
    "Menjaga keamanan data pelanggan sesuai kebijakan perusahaan.",
    "Meningkatkan efisiensi gudang dengan sistem penataan ulang.",
    "Menyiapkan laporan keuangan bulanan untuk manajemen.",
    "Mengusulkan perbaikan proses yang menghemat biaya operasional.",
    "Bergabung dengan tim QA untuk menguji fitur baru.",
    "Merancang antarmuka pengguna untuk aplikasi kasir.",
]


def _labeled_set() -> list[tuple[str, str]]:
    return [(b, "en") for b in EN_BULLETS] + [(b, "id") for b in ID_BULLETS]


def test_short_bullet_wordlist_fallback():
    """langdetect is known-weak here; the wordlist classifier must carry it."""
    assert wordlist_classify("Mengembangkan REST API dengan Django").lang == "id"
    assert wordlist_classify("Responsible for the reports").lang == "en"


def test_accuracy_on_labeled_set():
    labeled = _labeled_set()
    correct = sum(1 for text, expected in labeled if classify_language(text).lang == expected)
    accuracy = correct / len(labeled)
    # empirical acceptance bar for the fallback-assisted ensemble
    assert accuracy >= 0.80, f"lang_id accuracy {accuracy:.2f} below 0.80 on {len(labeled)} bullets"


def test_documented_accuracy_for_thesis(capsys):
    """Prints the confusion summary — the number goes into the evaluation chapter."""
    labeled = _labeled_set()
    errors = [(t[:50], expected, classify_language(t).lang) for t, expected in labeled
              if classify_language(t).lang != expected]
    accuracy = 1 - len(errors) / len(labeled)
    print(f"\nlang_id accuracy: {accuracy:.2%} ({len(labeled) - len(errors)}/{len(labeled)})")
    for t, exp, got in errors:
        print(f"  MISS [{exp}->{got}]: {t!r}")
    assert accuracy >= 0.80


def test_deterministic_labels():
    """langdetect is seeded; wordlists are static -> same input, same label."""
    for text, _ in _labeled_set():
        assert classify_language(text).lang == classify_language(text).lang


def test_empty_and_junk_inputs():
    assert classify_language("").lang == "other"
    assert classify_language("12345 !!!").lang in {"other", "en", "id", "mixed"}
