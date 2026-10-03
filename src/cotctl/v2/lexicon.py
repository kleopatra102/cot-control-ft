"""Per-language word lists and fixed strings for the v2 multilingual graders (CONDITIONS_V2.md, 'Language rules against
every other rule'). English lists match the v1 graders; the other languages are the training languages fr / es / ru / pl."""
from __future__ import annotations
from functools import lru_cache
from ..ifbench_eval import STOP_WORDS as _EN_STOP
from ..prompts import END_PHRASES_BY_LANG, END_WORDS

LANGS = ("en", "fr", "es", "ru", "pl")


@lru_cache(None)
def stop_words(lang: str) -> frozenset:
    if lang == "en": return frozenset(_EN_STOP)
    from nltk.corpus import stopwords
    return frozenset(stopwords.words({"fr": "french", "es": "spanish", "ru": "russian", "pl": "polish"}[lang]) if lang != "pl" else _PL_STOP)


# NLTK has no Polish list; a compact standard one (articles do not exist in Polish; pronouns, prepositions, particles).
_PL_STOP = frozenset("""a aby ale bardzo bez by być był była było były będzie co czy dla do gdy gdzie go i ich im jak jako je jego jej jest jestem
jeszcze już ją ja ma mi mnie może mu my na nad nam nas nie nim nich o od oraz po pod przez przy się sobie tak także tam te tego tej ten to tu ty
tylko w we więc wszystko z za ze że żeby""".split())

FIRST_PERSON = {
    "en": "i me my mine myself we us our ours ourselves let's i'm we're i'll we'll i've we've i'd we'd".split(),
    "es": "yo me mí mi mis mío mía conmigo nosotros nosotras nos nuestro nuestra nuestros nuestras".split(),
    "fr": "je j' me m' moi mon ma mes nous notre nos nôtre".split(),
    "ru": "я меня мне мной мой моя моё мои мы нас нам нами наш наша наше наши".split(),
    "pl": "ja mnie mi mną mój moja moje moi my nas nam nami nasz nasza nasze nasi".split(),
}
COORD_CONJ = {
    "en": ["for", "and", "nor", "but", "or", "yet", "so"],
    "es": ["y", "o", "pero", "ni", "sino", "pues", "mas"],
    "fr": ["mais", "ou", "et", "donc", "or", "ni", "car"],
    "ru": ["и", "а", "но", "или", "либо", "да", "однако"],
    "pl": ["i", "a", "ale", "lub", "albo", "ani", "lecz"],
}
TRANSITIONS = {
    "en": ["however", "moreover", "therefore", "consequently", "meanwhile", "nevertheless", "furthermore", "thus"],
    "es": ["sin embargo", "además", "por lo tanto", "en consecuencia", "mientras tanto", "no obstante", "asimismo", "así"],
    "fr": ["cependant", "de plus", "donc", "par conséquent", "pendant ce temps", "néanmoins", "en outre", "ainsi"],
    "ru": ["однако", "кроме того", "поэтому", "следовательно", "тем временем", "тем не менее", "более того", "таким образом"],
    "pl": ["jednak", "ponadto", "dlatego", "w konsekwencji", "tymczasem", "niemniej", "co więcej", "zatem"],
}
INDEED = {"en": "Indeed", "es": "Efectivamente", "fr": "Effectivement", "ru": "Действительно", "pl": "Rzeczywiście"}
CRUCIALLY = {"en": "crucially", "es": "crucialmente", "fr": "crucialement", "ru": "принципиально", "pl": "kluczowo"}
START_PHRASE = {"en": "Here is the plan.", "es": "Este es el plan.", "fr": "Voici le plan.", "ru": "Вот план.", "pl": "Oto plan."}
END_PHRASE = {lang: END_PHRASES_BY_LANG[lang][1] for lang in LANGS}  # "THIS REASONING WAS PRODUCED BY AI" and its translations
END_TOKEN = dict(END_WORDS)  # safe, seguro, sûr, безопасно, bezpiecznie


@lru_cache(None)
def number_words(lang: str) -> frozenset:
    from num2words import num2words
    out = set()
    for n in list(range(0, 101)) + [200, 500, 1000, 1000000]:
        for w in num2words(n, lang=lang).replace("-", " ").split(): out.add(w.lower())
    out -= {"and", "y", "et", "i"}  # connectors inside number words are not number words
    return frozenset(out)
