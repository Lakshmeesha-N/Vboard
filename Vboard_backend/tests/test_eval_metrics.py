import jiwer

from scripts.eval_audio import (
    check_formatting_difference,
    normalize_text,
)


def test_normalize_text_english():
    raw = "  Hello,   WORLD! It's a test...  "
    norm = normalize_text(raw)
    # Punctuation stripped, apostrophe preserved, lowercased, spaces collapsed
    assert norm == "hello world it's a test"


def test_normalize_text_indic_preserves_vowel_matras_and_viramas():
    # Kannada sentence with matras (ಾ, ಿ, ೇ, ೂ), viramas (್), and anusvara (ಂ)
    kannada_raw = "ಈ ತಿಂಗಳ ಸಂಬಳ ಬ್ಯಾಂಕ್ನಲ್ಲಿರುವ, ನನ್ನ ಖಾತೆಗೆ ಜಮಾ ಆಗಿದೆಯಾ?"
    kannada_norm = normalize_text(kannada_raw)

    # Question mark and comma should be stripped, matras and viramas must be preserved
    assert "?" not in kannada_norm
    assert "," not in kannada_norm
    assert "ಬ್ಯಾಂಕ್ನಲ್ಲಿರುವ" in kannada_norm
    assert "ಸಂಬಳ" in kannada_norm
    assert "ತಿಂಗಳ" in kannada_norm
    assert "ಖಾತೆಗೆ" in kannada_norm
    assert "ಜಮಾ" in kannada_norm
    assert "ಆಗಿದೆಯಾ" in kannada_norm

    # Hindi sentence with matras, halant (्), anusvara (ं), and punctuation (।, ?)
    hindi_raw = "क्या मुझे मेरी फसल बीमा पॉलिसी का विवरण मिलेगा? हाँ, बिल्कुल।"
    hindi_norm = normalize_text(hindi_raw)

    # Hindi purna viram (।) and punctuation marks stripped, matras preserved
    assert "?" not in hindi_norm
    assert "," not in hindi_norm
    assert "।" not in hindi_norm
    assert "पॉलिसी" in hindi_norm
    assert "मिलेगा" in hindi_norm
    assert "हाँ" in hindi_norm
    assert "बिल्कुल" in hindi_norm


def test_wer_and_cer_metrics():
    ref = normalize_text("the quick brown fox")
    hyp = normalize_text("the fast brown fox")

    wer = jiwer.wer(ref, hyp)
    cer = jiwer.cer(ref, hyp)

    # 1 word substitution out of 4 words -> 0.25 WER
    assert wer == 0.25
    assert 0.0 < cer < 1.0

    # Perfect match
    assert jiwer.wer(ref, ref) == 0.0
    assert jiwer.cer(ref, ref) == 0.0


def test_check_formatting_difference():
    # Case 1: Ref has Kannada words for numbers, hyp has Arabic digits -> flag
    ref1 = "ಮೂರು ಏಳು ನಾಲ್ಕು"
    hyp1 = "3 7 4"
    assert check_formatting_difference(ref1, hyp1) is True

    # Case 2: Ref has Hindi script, hyp has English Latin acronym (e.g. OTP) -> flag
    ref2 = "पासपोर्ट आवेदन"
    hyp2 = "पासपोर्ट id"
    assert check_formatting_difference(ref2, hyp2) is True

    # Case 3: Both already contain Latin letters / digits -> do not flag
    ref3 = "order 1234"
    hyp3 = "order 1234"
    assert check_formatting_difference(ref3, hyp3) is False

    # Case 4: Neither contains Latin letters or digits -> do not flag
    ref4 = "ನಮಸ್ಕಾರ ಶುಭೋದಯ"
    hyp4 = "ನಮಸ್ಕಾರ ಶುಭ ಮುಂಜಾನೆ"
    assert check_formatting_difference(ref4, hyp4) is False
