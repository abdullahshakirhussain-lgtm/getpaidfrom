"""Check a language's translations against the English before they can ship.

  python scripts/i18n_check.py es        (exit 1 on any problem)

For every translated line, and every interface string:
  - numbers: the same numbers, read with the language's own separators (24,000 -> 24.000 / 24 000; 4.5 -> 4,5)
  - codes and names: every currency code, acronym and service name in the English is still there
    (a few common acronyms have an accepted local form, listed in GLOSSARY)
  - negation: if the English says no / not / doesn't / without, the translation has a negation too
  - placeholders: interface strings keep exactly the same {placeholders}
  - completeness: every interface key and every content line has a translation, and none is left in English
Anything this can't judge (tone, grammar) is for a native reviewer; see docs/TRANSLATION.md.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from i18n import I18N, load_json, load_strings  # noqa: E402

# languages that write 24.000,5 or 24 000,5; the others keep English digits and separators
COMMA_DECIMAL = {"es", "fr", "pt", "id", "vi"}

BRANDS = ["PayPal", "Payoneer", "Wise", "Stripe", "Upwork", "Gumroad", "Lemon Squeezy", "Payhip", "Polar", "Paddle",
          "Dodo Payments", "Etsy", "Fiverr", "Skrill", "Amazon", "Shopify", "Western Union", "Remitly", "Binance",
          "Google", "Apple", "Deel", "Revolut", "Airtm", "Pioneer", "WorldRemit", "MoneyGram", "Visa", "Mastercard",
          "Flutterwave", "Paystack", "M-Pesa", "Razorpay", "JazzCash", "Easypaisa", "bKash", "Payeer", "Alipay", "WeChat"]

# English acronym -> accepted forms per language (any one may appear instead of the English)
GLOSSARY = {
    "VAT": {"es": ["IVA"], "fr": ["TVA"], "pt": ["IVA"], "ar": ["ضريبة القيمة المضافة", "قيمة مضافة"], "ur": ["ویٹ", "سیلز ٹیکس"],
            "bn": ["ভ্যাট", "মূসক"], "id": ["PPN"], "vi": ["GTGT", "VAT"]},
    "EU": {"es": ["UE"], "fr": ["UE"], "pt": ["UE"], "ar": ["الاتحاد الأوروبي", "لاتحاد الأوروبي"], "ur": ["یورپی یونین"], "bn": ["ইউরোপীয় ইউনিয়ন"],
           "id": ["UE", "Uni Eropa"], "vi": ["EU", "Liên minh châu Âu"]},
    "UN": {"es": ["ONU"], "fr": ["ONU"], "pt": ["ONU"], "ar": ["الأمم المتحدة"], "ur": ["اقوام متحدہ"], "bn": ["জাতিসংঘ"],
           "id": ["PBB"], "vi": ["Liên Hợp Quốc", "LHQ"]},
    "US": {"es": ["EE. UU.", "Estados Unidos", "estadounidense"], "fr": ["États-Unis", "américain", "américaine", "américains"],
           "pt": ["EUA", "Estados Unidos", "americano", "americana"], "ar": ["الأمريكي", "الأمريكية", "الولايات المتحدة", "أمريكي", "أمريكية"],
           "ur": ["امریکی", "امریکہ"], "bn": ["মার্কিন", "যুক্তরাষ্ট্র"], "id": ["AS", "Amerika Serikat"], "vi": ["Mỹ", "Hoa Kỳ"]},
    "UK": {"es": ["Reino Unido", "británico", "británica"], "fr": ["Royaume-Uni", "britannique"], "pt": ["Reino Unido", "britânico", "britânica"],
           "ar": ["المملكة المتحدة", "البريطاني", "البريطانية"], "ur": ["برطانیہ", "برطانوی"], "bn": ["যুক্তরাজ্য", "ব্রিটিশ"],
           "id": ["Inggris"], "vi": ["Anh", "Vương quốc Anh"]},
    "ID": {"es": ["identificación", "identidad", "documento", "elector", "cédula", "carné", "carnet", "DNI"], "fr": ["identité", "pièce", "électeur"], "pt": ["identidade", "documento", "identificação", "eleitor"],
           "ar": ["هوي", "تعريف", "معرّف", "معرف", "ناخب", "القومي", "ضريبي", "البطاقة الشخصية", "البطاقة الوطنية"], "ur": ["شناخت", "شناختی"], "bn": ["পরিচয়"], "id": ["identitas", "KTP"], "vi": ["giấy tờ", "định danh", "căn cước", "CCCD"]},
    "UNCTAD": {"fr": ["CNUCED"], "es": ["UNCTAD"], "ar": ["الأونكتاد"], "ur": ["UNCTAD"], "bn": ["UNCTAD"]},
    "SME": {"es": ["pyme", "PYME"], "fr": ["PME"], "pt": ["PME"], "ar": ["الصغيرة والمتوسطة"], "id": ["UMKM"], "vi": ["DNNVV"]},
    "SMEs": {"es": ["pymes", "PYMES"], "fr": ["PME"], "pt": ["PME", "PMEs"], "ar": ["الصغيرة والمتوسطة"], "id": ["UMKM"], "vi": ["DNNVV"]},
    "NGO": {"es": ["ONG"], "fr": ["ONG"], "pt": ["ONG"], "ar": ["منظمة غير حكومية", "المنظمات غير الحكومية"], "id": ["LSM"], "vi": ["NGO", "tổ chức phi chính phủ"]},
    "ICT": {"es": ["TIC"], "fr": ["TIC"], "pt": ["TIC"], "ar": ["تكنولوجيا المعلومات والاتصالات", "تقنية المعلومات والاتصالات"],
            "ur": ["آئی سی ٹی", "انفارمیشن ٹیکنالوجی"], "bn": ["আইসিটি", "তথ্য ও যোগাযোগ প্রযুক্তি"], "id": ["TIK"], "vi": ["CNTT-TT", "ICT"]},
    "FX": {"es": ["divisas", "cambio", "cambiario"], "fr": ["devises", "change"], "pt": ["câmbio", "divisas", "moeda estrangeira", "cambial"], "ar": ["الصرف", "العملات", "عملة أجنبية", "العملة الأجنبية"], "ur": ["زرمبادلہ"],
           "bn": ["বৈদেশিক মুদ্রা"], "id": ["valas", "devisa"], "vi": ["ngoại hối", "ngoại tệ"]},
    "LLC": {"es": ["SRL", "S.R.L.", "LLC"], "fr": ["SARL", "LLC"], "pt": ["Ltda", "LLC"], "ar": ["ذات مسؤولية محدودة", "LLC"],
            "ur": ["LLC"], "bn": ["LLC"], "id": ["LLC", "PT"], "vi": ["LLC", "TNHH"]},
    "MoR": {"es": ["vendedor registrado"], "fr": ["vendeur officiel"], "pt": ["vendedor oficial"], "ar": ["البائع الرسمي"]},
    "IT": {"es": ["TI", "informática", "tecnologías de la información"], "fr": ["informatique", "numérique", "TI"],
           "pt": ["TI", "informática", "tecnologia da informação"], "ar": ["تقنية المعلومات", "تكنولوجيا المعلومات"],
           "ur": ["آئی ٹی"], "bn": ["আইটি", "তথ্যপ্রযুক্তি"], "id": ["TI", "teknologi informasi"], "vi": ["CNTT", "công nghệ thông tin"]},
    "UAE": {"es": ["EAU", "Emiratos"], "fr": ["EAU", "Émirats"], "pt": ["EAU", "Emirados"], "ar": ["الإمارات"], "ur": ["امارات"],
            "bn": ["আমিরাত"], "id": ["UEA", "Emirat"], "vi": ["UAE", "Các Tiểu vương quốc"]},
    "EEA": {"es": ["EEE"], "fr": ["EEE"], "pt": ["EEE"], "ar": ["المنطقة الاقتصادية الأوروبية"], "ur": ["یورپی اقتصادی"],
            "bn": ["ইউরোপীয় অর্থনৈতিক"], "id": ["EEA"], "vi": ["EEA"]},
    "GDPR": {"es": ["RGPD"], "fr": ["RGPD"], "pt": ["RGPD"], "ar": ["اللائحة العامة لحماية البيانات"], "id": ["GDPR"], "vi": ["GDPR"]},
    "ECOWAS": {"es": ["CEDEAO"], "fr": ["CEDEAO"], "pt": ["CEDEAO"], "ar": ["إيكواس"], "ur": ["ایکوواس"], "bn": ["ইকোওয়াস"]},
    "FATF": {"es": ["GAFI"], "fr": ["GAFI"], "pt": ["GAFI"], "ar": ["مجموعة العمل المالي"], "ur": ["ایف اے ٹی ایف"]},
    "MSME": {"es": ["mipyme", "MIPYME"], "fr": ["MPME", "TPME"], "pt": ["MPME"], "ar": ["متناهية الصغر"], "id": ["UMKM"], "vi": ["DNNVV"]},
    "DPR": {"es": ["RPD"], "fr": ["RPD"], "pt": ["RPD"], "ar": ["دونيتسك"], "ur": ["ڈونیٹسک"], "bn": ["দোনেৎস্ক"], "id": ["Donetsk"], "vi": ["Donetsk"]},
    "LPR": {"es": ["RPL"], "fr": ["RPL"], "pt": ["RPL"], "ar": ["لوغانسك"], "ur": ["لوہانسک"], "bn": ["লুহানস্ক"], "id": ["Luhansk"], "vi": ["Luhansk"]},
    "POS": {"es": ["TPV"], "fr": ["TPE", "terminal de paiement"], "pt": ["POS", "maquininha"], "ar": ["نقاط البيع"],
            "ur": ["پوائنٹ آف سیل", "POS"], "bn": ["POS"], "id": ["POS", "EDC"], "vi": ["POS"]},
    "SaaS": {},
}

NEG_EN = re.compile(r"\b(no(?!\.\s*\d)|not|n't|cannot|can't|without|never|none|nor|nothing|unavailable)\b|n't\b", re.I)
NEG = {
    "es": r"\b(no|ni|sin|nunca|ningún|ninguna|ninguno|nada|tampoco|nadie|ausencia|imposible)\b",
    "fr": r"\b(ne|n'|n’|pas|sans|aucun|aucune|jamais|non|ni|rien|plus|impossible|muettes?|introuvable|indisponibles?|interdite?s?|absente?s?|absence|inutiles?|inutilisables?|sauf)\b|\bn['’]",
    "pt": r"(?<!\w)(não|nao|sem|nenhum|nenhuma|nunca|nem|nada|indisponíve(?:l|is)|inúte(?:l|is)|ausência|exceto|impossível|fora)(?!\w)",
    "ar": r"(?<!\w)[وف]?(لا|لم|لن|ليس|ليست|غير|بدون|دون|بلا|تعذّر|تعذر|يتعذر|يتعذّر|عدم|ممنوع|محظور|إلا|سوى|خارج|لسنا|ألا|ألّا|غياب|انعدام)(?!\w)",
    "ur": r"نہیں|نہ |بغیر|بلا|کوئی نہیں",
    "bn": r"না|নেই|নয়|ছাড়া|নি\b|নি |নি।|নি,",
    "id": r"\b(tidak|tak|bukan|tanpa|belum|jangan)\b",
    "vi": r"\b(không|chưa|chẳng|chả)\b",
}
NUM_EN = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
NUM_COMMA = re.compile(r"\d{1,3}(?:[.   ]\d{3})+(?:,\d+)?|\d+(?:,\d+)?")
ACRO = re.compile(r"(?<![\w-])(?:[A-Z]{2,}[A-Za-z0-9]*|[A-Z][a-z]*[A-Z][A-Za-z0-9]*|[A-Z]+-[A-Z0-9]+)(?![\w-])")


# "1 billion" is written "1.000 millones", "1 milliard", "1 tỷ"...: compare in millions
BILLION = {"en": r"billion|bn", "es": r"mil millones", "fr": r"milliards?", "pt": r"bilh(?:ão|ões)|mil milhões",
           "ar": r"مليارات|مليار", "ur": r"ارب", "bn": r"বিলিয়ন|শত কোটি", "id": r"miliar", "vi": r"tỷ"}


# Arabic and Urdu say "two months" with a dual form, not the digit
DUAL = {"ar": r"شهرين|يومين|سنتين|عامين|ساعتين|أسبوعين|شهران|يومان|سنتان|عامان"}


def numbers(text, lang):
    if lang in DUAL:
        text = re.sub(DUAL[lang], " 2 ", text)
    dec = "," if lang in COMMA_DECIMAL else "."
    text = re.sub(rf"(\d+(?:\{dec}\d+)?)\s*(?:{BILLION[lang]})(?!\w)",
                  lambda m: f" {float(m.group(1).replace(',', '.')) * 1000:g} ", text)
    if lang in COMMA_DECIMAL:
        return Counter(float(re.sub(r"[.   ]", "", m).replace(",", ".")) for m in NUM_COMMA.findall(text))
    return Counter(float(m.replace(",", "")) for m in NUM_EN.findall(text))


def tokens(en):
    # an amount glued to its currency ("RM30") only needs the currency to survive ("30 RM")
    found = {re.sub(r"^([A-Z]{2,})\d+$", r"\1", f) for f in ACRO.findall(en)}
    found |= {b for b in BRANDS if re.search(rf"(?<!\w){re.escape(b)}(?!\w)", en)}
    # a brand like "PayPal" also matches ACRO; keep the longest names only
    return {f for f in found if not any(f != g and f in g for g in found)}


def verbatim_out(en, tr):
    """Numbers written the same way in both (law numbers like 25.326, decree 45/2021) are set aside first."""
    for m in sorted(set(re.findall(r"\d+(?:[.,/-]\d+)+", en)), key=len, reverse=True):
        pat = rf"(?<![\d.,]){re.escape(m)}(?![\d]|[.,]\d)"
        if re.search(pat, tr):
            en, tr = re.sub(pat, " ", en), re.sub(pat, " ", tr)
    return en, tr


def problems(en, tr, lang):
    out = []
    en, tr = verbatim_out(en, tr)
    if numbers(en, "en") != numbers(tr, lang):
        out.append(f"numbers differ: {sorted(numbers(en, 'en').elements())} vs {sorted(numbers(tr, lang).elements())}")
    for tok in sorted(tokens(en)):
        alts = [tok] + GLOSSARY.get(tok, {}).get(lang, []) + ([tok[:-1]] if re.fullmatch(r"[A-Z]{2,}s", tok) else [])
        if not any(a.casefold() in tr.casefold() for a in alts):
            out.append(f"missing '{tok}'")
    if NEG_EN.search(en) and not re.search(NEG[lang], tr, re.I):
        out.append("English has a negation, translation has none")
    if tr.strip() == en.strip() and re.search(r"[a-z]{4,} [a-z]{4,}", en):
        out.append("left in English")
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    lang = sys.argv[1]
    errors = []
    allow = set()
    allow_file = I18N / f"allow.{lang}.txt"  # "<id> <check>" lines a reviewer has signed off on
    if allow_file.exists():
        allow = {tuple(x.split(" ", 1)) for x in allow_file.read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")}
    en_ui = {k: v for k, v in load_json(I18N / "ui.en.json").items() if not k.startswith("_")}
    ui = {k: v for k, v in load_json(I18N / f"ui.{lang}.json").items() if not k.startswith("_")}
    for k, en in en_ui.items():
        if k not in ui:
            errors.append(f"ui {k}: missing")
            continue
        ph_en, ph_tr = sorted(re.findall(r"\{\w+\}", en)), sorted(re.findall(r"\{\w+\}", ui[k]))
        if ph_en != ph_tr:
            errors.append(f"ui {k}: placeholders {ph_en} vs {ph_tr}")
        errors += [f"ui {k}: {p}" for p in problems(re.sub(r"\{\w+\}", "", en), re.sub(r"\{\w+\}", "", ui[k]), lang)
                   if (f"ui.{k}", p.split(":")[0]) not in allow]
    errors += [f"ui {k}: not in English" for k in ui if k not in en_ui and not k.startswith("_")]

    source = {}
    for line in (I18N / "source.tsv").read_text(encoding="utf-8").splitlines():
        k, _, en = line.partition("\t")
        source[k] = en
    strings = load_strings(lang)
    for k, en in source.items():
        if k not in strings:
            errors.append(f"{k}: not translated: {en[:70]}")
            continue
        for p in problems(en, strings[k], lang):
            if (k, p.split(":")[0]) not in allow:
                errors.append(f"{k}: {p}\n    en: {en}\n    {lang}: {strings[k]}")
    stale = [k for k in strings if k not in source]
    sw = I18N / f"search.{lang}.json"
    if not sw.exists():
        errors.append(f"search.{lang}.json missing")
    print("\n".join(errors) if errors else "", end="\n" if errors else "")
    print(f"{lang}: {len(strings)}/{len(source)} lines, {len(ui)}/{len(en_ui)} interface strings, "
          f"{len(errors)} problems, {len(stale)} unused (English changed)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
