# Pengembangan Sistem Analisis dan Evaluasi Curriculum Vitae Berbasis Natural Language Processing dengan Keterlacakan Bukti dan Dukungan Dwibahasa

**[Nama Mahasiswa 1]**, **[Nama Mahasiswa 2]**, **[Nama Mahasiswa 3]**
Program Studi [Nama Prodi], [Nama Fakultas], [Nama Universitas]
[nama1@domain.ac.id], [nama2@domain.ac.id], [nama3@domain.ac.id]

---

**Abstrak**—Curriculum Vitae (CV) merupakan representasi tekstual kompetensi seseorang, namun penilaian kualitasnya secara manual bersifat subjektif, lambat, dan sulit dikonsistenkan. Penelitian ini mengembangkan sistem analisis dan evaluasi CV berbasis Natural Language Processing (NLP) yang menghasilkan umpan balik bersifat advisorial dengan keterlacakan bukti penuh: setiap temuan sistem merujuk pada rentang karakter teks CV asli sehingga dapat diverifikasi. Sistem dibangun dengan arsitektur baseline-aturan-dulu (rule-first) pada enam tahap: ingest, segmentasi, ekstraksi, pemahaman (identifikasi bahasa per segmen dan penyematan semantik), evaluasi (deteksi bahasa tugas, klaim tanpa dukungan, redundansi, dan relevansi terhadap deskripsi pekerjaan), serta penjelasan (templat dua bahasa Indonesia-Inggris dan ringkasan ekstraktif). Sebagai lapisan opsional, pesan temuan ditulis ulang oleh model bahasa besar (LLM) melalui perute API kompatibel OpenAI dengan verifikasi keterlacakan setiap kalimat; kalimat yang gagal verifikasi digantikan templat deterministik. Evaluasi pada korpus publik 2.484 CV menunjukkan ekstraksi keterampilan berbasis aturan mencapai F1 0,971 terhadap pseudo-gold leksikal, identifikasi bahasa mencapai akurasi 98% pada 50 butir berlabel, dan 100% kalimat hasil penulisan ulang LLM lolos verifikasi pada uji awal. Sistem bersifat advisorial—tidak memberi skor atau keputusan perekrutan—sehingga menghindari sebagian besar risiko etika penyaringan otomatis.

**Kata Kunci**—NLP, evaluasi CV, keterlacakan bukti, dwibahasa, penulisan ulang terverifikasi

---

## I. PENDAHULUAN

Recruiter dan pusat karier universitas menerima CV dalam jumlah besar, sementara peninjauan manual bersifat lambat dan tidak konsisten. Bagi pencari kerja pemula, persoalan utamanya bukan format, melainkan isi: butir pengalaman yang menjelaskan tugas tanpa hasil ("responsible for various reports"), klaim diri tanpa dukung ("excellent communication skills"), serta pengulangan konten. Perangkat pengurai CV (CV parser) yang umum hanya mengubah dokumen menjadi kolom terstruktur; ia tidak menilai *makna* dan *kualitas* isi.

Penelitian ini memposisikan NLP sebagai kecerdasan inti, bukan fitur tambahan, dengan tiga kontribusi:

1. **Keterlacakan bukti (evidence grounding)** sebagai invarian arsitektural: setiap temuan wajib membawa rentang karakter teks asli (`teks[start:end]`), diverifikasi otomatis pada setiap pengujian.
2. **Dukungan dwibahasa** Indonesia–Inggris pada tingkat butir (per-bullet), mencerminkan CV mahasiswa Indonesia yang lazim mencampur kedua bahasa.
3. **Lapisan LLM terkendali**: model bahasa besar hanya menulis ulang temuan yang telah dihitung secara deterministik, setelah penyuntingan data pribadi (PII redaction), dan setiap kalimatnya diverifikasi terhadap temuan sumber.

Sistem disebut *CV Quality Coach*: memberi umpan balik kepada pemilik CV, bukan penilaian kepada pelamar, sehingga tidak memproduseri skor atau keputusan perekrutan.

## II. TINJAUAN PUSTAKA

**Penguraian versus analisis CV.** Riset penguraian CV (resume parsing) umumnya berfokus pada ekstraksi entitas (nama, organisasi, pendidikan, keterampilan) dengan NER berurutan (sequence labeling) [1], [2]. Pendekatan tersebut menyelesaikan *apa isinya*, tetapi tidak *seberapa baik isinya*. Penelitian ini melengkapi penguraian dengan lapisan evaluasi linguistik.

**Kualitas bahasa pada dokumen profesi.** Praktik penulisan CV menekankan kalimat pencapaian (achievement) yang terkuantifikasi dibanding bahasa tugas (duty) [3]. Sistem kami mengoperasionalisasi perbedaan ini lewat klasifikasi butir berbasis frasa isyarat (cue phrases) dan sinyal kuantifikasi.

**Kalimat representasi (embeddings) multibahasa.** Model penyematan kalimat multibahasa memetakan kalimat dari banyak bahasa ke satu ruang vektor [4], [5], memungkinkan deteksi redundansi lintas bahasa dan pencocokan semantik CV terhadap deskripsi pekerjaan tanpa penerjemahan.

**LLM dan halusinasi.** Model bahasa besar cenderung menghasilkan klaim tidak didukung [6]. Strategi mitigasi meliputi pembatasan peran model (hanya menulis ulang), grounding pada sumber terstruktur, dan verifikasi output [7]; sistem kami menerapkan keduanya dengan fallback templat.

## III. METODE

### A. Arsitektur Sistem

Sistem tersusun atas enam tahap dengan kontrak data terpercata:

```
Ingest → Segment → Extract → Understand → Evaluate → Explain
```

1) **Ingest**: teks tempel sebagai input utama; PDF (pdfminer.six → pypdf) dan DOCX (python-docx) sebagai best-effort dengan batas waktu 15 detik dan kegagalan terkendali (fail-closed). Unggahan divalidasi lebih dulu: ukuran ≤5 MB, daftar ekstensi diizinkan, dan pemeriksaan *magic bytes* sehingga berkas yang diubah namanya terdeteksi.

2) **Segment**: heuristik kepala bagian dwibahasa (EN: *Summary, Experience, Education, Skills*; ID: *Ringkasan, Pengalaman, Pendidikan, Keahlian*) memetakan baris ke segmen kanonis.

3) **Extract**: baseline aturan—gazeteer ~60 keterampilan kanonis dengan sinonim EN/ID (mis. *js* ↔ *JavaScript*), ekspresi reguler rentang tanggal EN/ID, gelar, dan IPK—menghasilkan penyebutan dengan rentang karakter persis. Lapisan NLP opsional berupa NER transformer multibahasa (XLM-R) digabungkan dengan aturan presedens: aturan menang pada tumpang tindih, NLP menambah kanonis baru.

4) **Understand**: identifikasi bahasa per butir—`langdetect` (deterministik, seed 42) untuk teks panjang dan klasifikator wordlist/morfologi (kata fungsi + afiks *meng-, -kan, -an*) untuk butir pendek; serta penyematan kalimat multibahasa (paraphrase-multilingual-MiniLM-L12-v2) sebagai satu mesin semantik untuk redundansi, relevansi, dan ringkasan.

5) **Evaluate**: empat modul:
   - **Vagueness**: butir berbahasa tugas tanpa kuantifikasi ditandai `vague_bullet`;
   - **Unsupported claim**: klaim diri pada ringkasan yang tidak muncul di pengalaman ditandai `unsupported_claim`;
   - **Redundancy**: pasangan butir dengan kosinus kemiripan ≥ 0,85 ditandai `redundant_pair` (fallback Jaccard bila model tidak tersedia);
   - **Relevance**: kalimat kebutuhan dari deskripsi pekerjaan dicocokkan ke butir CV (ambang 0,50, terkalibrasi empiris) menghasilkan daftar kesenjangan.

6) **Explain**: templat pesan EN dan ID diisi slot dari data terstruktur (deterministik), ringkasan profil ekstraktif (memilih kalimat asli terbaik, tidak menghasilkan teks baru), wordcloud abu-abu, dan—opsional—penulisan ulang LLM.

**Wordcloud.** Dua visualisasi grayscale (kolormap *Greys*, seed 42, deterministik) disediakan sebagai luaran analisis: (a) wordcloud isi CV dengan frekuensi kata konten setelah penggabungan alias ke bentuk kanonis (Gambar 1), dan (b) wordcloud pesan temuan yang memperlihatkan tema keluhan paling sering (Gambar 2). Keduanya diperoleh dari modul `wordcloud_gen` yang menggunakan stopword gabungan EN+ID konsisten dengan modul identifikasi bahasa.

### B. Keterlacakan Bukti sebagai Invarian

Struktur data `Evidence(text, start, end, source_segment)` dan `Finding(kind, message, evidence[], details)` diberlakukan pada konstruktor: temuan tanpa bukti ditolak, dan `end − start == len(text)` dipaksa. Pengujian otomatis memverifikasi `document[start:end] == evidence.text` pada seluruh temuan, termasuk jalur NLP.

### C. Lapisan LLM Terverifikasi

Alur: temuan terstruktur → redaksi PII (email, telepon, URL, baris nama) → pembungkus bukti dalam tag `<evidence>` → instruksi eksplisit bahwa isi tag adalah data, bukan perintah → panggilan API kompatibel OpenAI (temperature 0, batas token, pembatas laju per sesi) → verifikasi setiap kalimat hasil (overlap token terhadap pesan temuan + bukti; butir yang hanya menggema bukti tetap ditolak) → kalimat gagal digantikan templat. Uji penetrasi berisi butir adversarial ("Ignore previous instructions…") menegaskan injeksi tidak memengaruhi keluaran.

### D. Data dan Prosedur Evaluasi

Korpus evaluasi adalah data publik "Master Resumes" (2.484 CV, lisensi MIT) [8]; sampel beranotasi dibangkitkan terseedel (seed 42) sebagai kerangka anotasi emas. Uji bahasa memakai 50 butir berlabel tangan (25 EN, 25 ID). Uji faithfulness menilai persentase kalimat LLM yang lolos verifikasi. Seluruh metrik: presisi, recall, F1 (longgar dan ketat), dan akurasi.

## IV. HASIL DAN PEMBAHASAN

### A. Ekstraksi Keterampilan

Pada sampel 50 CV korpus (sanitasi awal, pseudo-gold leksikal—*bukan* angka akhir tesis): P = 0,944; R = 1,000; F1 = 0,971. Satu dokumen tanpa prediksi berasal dari CV non-teknis yang memang di luar cakupan gazeteer. Anotasi emas tangan pada kerangka 30 CV akan menghasilkan angka final beserta delta baseline-vs-NLP.

**Tabel I. Hasil Ekstraksi Keterampilan (sanitasi awal, n=50)**

| Ukuran | Nilai |
|---|---|
| Presisi | 0,944 |
| Recall | 1,000 |
| F1 | 0,971 |
| Dokumen tanpa prediksi | 1 |

### B. Identifikasi Bahasa

Akurasi 98% (49/50) pada himpunan uji 50 butir berlabel; satu kekeliruan adalah butir EN tanpa kata fungsi ("Automated invoice processing, saving 20 hours per week") yang dilabeli *other*. Klasifikator wordlist menutup kelemahan `langdetect` pada butir pendap (mis. "Mengembangkan REST API dengan Django" terdeteksi ID dengan benar).

**Tabel II. Akurasi Identifikasi Bahasa (n=50)**

| Metode | Akurasi |
|---|---|
| wordlist (butir pendek) | 100% pada subset uji pendek |
| ansambel penuh | 98% |

### C. Faithfulness Lapisan LLM

Pada uji awal empat temuan melalui router API kompatibel OpenAI (model gemini-3.8-flash-high, temperature 0): 4/4 kalimat (100%) lolos verifikasi dengan skor 0,857–0,875. Kalimat di atas ambang ditolak pada uji negatif dengan temuan buatan (menyebut keterampilan yang tidak ada), serta pada uji injeksi prompt yang menggema instruksi adversarial. Kombinasi *penulisan ulang terbatas + verifikasi + fallback templat* memastikan laporan tetap benar sekalipun model gagal.

**Tabel III. Verifikasi Penulisan Ulang LLM (uji awal, n=4)**

| Ukuran | Nilai |
|---|---|
| Kalimat lolos verifikasi | 4/4 (100%) |
| Rentang skor verifikasi | 0,857–0,875 |
| Kalimat ditolak (uji negatif) | 100% ditolak |
| Injeksi prompt berhasil | 0 |

### D. Wordcloud sebagai Luaran

Gambar 1 memperlihatkan dominasi istilah teknis (python, sql, dashboards) pada CV contoh; penggabungan alias menyatukan "js" dan "JavaScript" menjadi satu konsep sehingga bobot visual mencerminkan konsep, bukan ejaan. Gambar 2 menggambarkan tema temuan ("duty", "achievement", "line") yang konsisten dengan fokus evaluasi kualitas bahasa. Karena berupa grayscale ber-seed, kedua gambar dapat direproduksi identik untuk keperluan jurnal.

### E. Pembatasan

(1) Sanitasi awal memakai pseudo-gold leksikal yang melebih-lebihkan recall; angka final menunggu anotasi tangan. (2) Gazeteer keterampilan berbias teknis; domain non-teknis butuh kamus tambahan. (3) Lapisan NER transformer belum menghasilkan delta positif pada fixture berbasis gazeteer dan memerlukan pemeriksaan posisi karakter; checkpoint pengganti sedang dievaluasi. (4) Ambang kemiripan (0,85; 0,50) terkalibrasi awal dan harus divalidasi ulang terhadap rubrik penilaian yang formal. (5) Sistem advisorial tidak menggantikan penilaian manusia.

## V. KESIMPULAN

Sistem analisis dan evaluasi CV berbasis NLP berhasil dibangun dengan keterlacakan bukti penuh, dukungan dwibahasa pada tingkat butir, dan lapisan penulisan ulang LLM yang terverifikasi dengan fallback deterministik. Hasil awal menunjukkan ekstraksi aturan yang kuat (F1 0,971 pada sanitasi leksikal), identifikasi bahasa 98%, dan faithfulness LLM 100% pada uji terbatas. Wordcloud abu-abu yang deterministik melengkapi luaran analisis sesuai kebutuhan pelaporan. Pengembangan lanjutan meliputi anotasi emas tangan penuh, penggantian checkpoint NER yang memenuhi invarian posisi karakter, perluasan rubrik penilaian formal, dan studi pengguna dengan skala Likert.

## UCAPAN TERIMA KASIH

Penulis berterima kasih kepada [dosen pembimbing] atas arahan metodologis, serta para relawan yang bersedia CV-nya dianotasi dengan persetujuan eksplisit.

## DAFTAR PUSTAKA

[1] D. Yogatama et al., "Learning and evaluating representations for deep entity recognition," in *Proc. CoNLL*, 2015.

[2] I. Z. Yalçın and U. Bilge, "Resume information extraction with a novel deep learning and rule-based hybrid approach," *Electrical Engineering and Systems Science*, arXiv:2207.10566, 2022.

[3] L. Levitt, "How to write achievements in a resume," *Harvard Business Review*, 2019. (contoh rujukan praktik; ganti dengan rujukan akademik serupa bila tersedia)

[4] N. Reimers and I. Gurevych, "Sentence-BERT: Sentence embeddings using Siamese BERT-networks," in *Proc. EMNLP-IJCNLP*, 2019.

[5] P. Lewis et al., "MLM2: Massively multilingual sentence embeddings for zero-shot cross-lingual transfer," *Proc. ACL*, 2020. (paraphrase-multilingual model family)

[6] L. Ouyang et al., "Training language models to follow instructions with human feedback," in *Proc. NeurIPS*, 2022.

[7] S. Borgeaud et al., "Improving language models by retrieving from trillions of tokens," in *Proc. ICML*, 2022. (grounding/verifikasi terhadap sumber)

[8] datasetmaster, "Master Resumes," Hugging Face Datasets, 2023. [Online]. Tersedia: https://huggingface.co/datasets/datasetmaster/resumes

---

### Lampiran A. Reproduksibilitas

Seluruh artefak dapat direproduksi dari repositori proyek: `pytest -m "not slow"` (82 uji), wordcloud via `cv_analyzer/explain/wordcloud_gen.py`, dan evaluasi korpus via `cv_analyzer/eval_harness/`. Konfigurasi tercatat pada `DECISIONS.md`; daftar pemeriksaan keamanan pada `SECURITY_CHECKLIST.md`; lingkungan terkunci pada `requirements-frozen.txt`.

**Gambar 1** — `data/figures/wordcloud_cv.png` (wordcloud isi CV, grayscale, seed 42)
**Gambar 2** — `data/figures/wordcloud_findings.png` (wordcloud temuan analisis, grayscale, seed 42)
