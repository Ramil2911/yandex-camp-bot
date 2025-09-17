import re
import unicodedata
from app.utils.log import logger, log_security_event

MALICIOUS_PROMPT_PATTERNS = [

    # Игнор/перезапись правил
    re.compile(r"\b(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above)\s+(instructions|rules|prompts)\b", re.I|re.U),
    re.compile(r"\b(overwrite|override)\s+(your\s+)?(system|safety|guardrail|policy)\b", re.I|re.U),
    re.compile(r"\b(игнориру(й|йте)|забудь|отмени)\s+(все\s+)?(предыдущ(ие|ие указания)|инструкци(и|ю)|правила)\b", re.I|re.U),
    re.compile(r"\bобойди(те)?\s+(политик(у|и)|ограничени(е|я)|правил(а)?)\b", re.I|re.U),

    # Обход модерации/защит
    re.compile(r"\b(bypass|circumvent|jailbreak|exploit)\s+(the\s+)?(filters?|moderation|guardrails?|safety)\b", re.I|re.U),
    re.compile(r"\bобход(ить|а)\s+(фильтр(ы)?|модерац(ию|ии)|защит(у|ы))\b", re.I|re.U),
    re.compile(r"\bбез\s+ограничени(й|я)\b", re.I|re.U),

    # Режимы DAN/DevMode/аморальные роли
    re.compile(r"\b(act\s+as|you\s+are)\s+(DAN|Do\s*Anything\s*Now)\b", re.I|re.U),
    re.compile(r"\b(developer\s*mode|dev\s*mode)\b", re.I|re.U),
    re.compile(r"\b(role[-\s]*play|pretend\s+to\s+be)\s+(an?\s+)?(unrestricted|amoral|unsafe)\s+(ai|assistant)\b", re.I|re.U),
    re.compile(r"\bсыграй\s+ролью?\s+(аморального|безоговорочно\s+послушного|неограниченного)\s+ИИ\b", re.I|re.U),

    # Раскрытие системного промпта/правил
    re.compile(r"\b(show|reveal|dump|print)\s+(your\s+)?(system|hidden|internal)\s+(prompt|instructions?|messages?)\b", re.I|re.U),
    re.compile(r"\bраскро(й|йте)\s+(системн(ый|ые)\s+)?(промпт|подсказк(у|и)|инструкци(ю|и)|правил(а)?)\b", re.I|re.U),
    re.compile(r"\bвывед(и|ите)\s+(системн(ый|ые)\s+)?(промпт|правила|инструкци(ю|и))\b", re.I|re.U),

    # Запросы ключей/секретов
    re.compile(r"\b(api\s*key|secret\s*key|access\s*token|password|passphrase|private\s*key)\b", re.I|re.U),
    re.compile(r"\b(скажи|сообщи|выдай)\s+(мне\s+)?(api\s*key|секретн(ый|ые)\s+ключ(и)?|парол(ь|и)|токен)\b", re.I|re.U),

    # Цепочка рассуждений/скретчпад
    re.compile(r"\b(show|reveal|print|explain)\s+(your\s+)?(chain[-\s]*of[-\s]*thought|scratchpad|hidden\s+reasoning)\b", re.I|re.U),
    re.compile(r"\bпокажи\s+(сво(ю|и)\s+)?(цепочк(у|и)\s+рассуждени(й|я)|черновик|скретчпад|скрытые\s+мысли)\b", re.I|re.U),

    # Отключение фильтров/безопасности
    re.compile(r"\bdisable|turn\s*off|remove\s+(the\s+)?(filter|safety|guardrails?)\b", re.I|re.U),
    re.compile(r"\bотключ(и|ите|ай)\s+(фильтр(ы)?|ограничени(я|е)|безопасност(ь|и))\b", re.I|re.U),

    # Социнжиниринг/исключение из правил
    re.compile(r"\b(as\s+an?\s+exception|just\s+this\s+once|no\s+limits)\b", re.I|re.U),
    re.compile(r"\bкак\s+исключени(е|я)|только\s+сейчас|без\s+ограничени(й|я)\b", re.I|re.U),

    # «Переведи/перескажи, но верни запрещённое»
    re.compile(r"\b(just|only)\s+(translate|summarize)\s+but\s+(keep|include)\s+(the\s+)?(instructions|secrets|keys)\b", re.I|re.U),
    re.compile(r"\bпросто\s+переведи|только\s+перефразируй.*(но|и)\s+(сохрани|верни)\s+(инструкции|секрет(ы)?|ключ(и)?)\b", re.I|re.U),

    # Длинные base64/hex блоки (эксфиль/внедрение)
    re.compile(r"\b[A-Za-z0-9+/]{200,}={0,2}\b"),
    re.compile(r"\b(?:[0-9A-Fa-f]{2}\s*){64,}\b"),

    # Без морали/этики, игнор политики
    re.compile(r"\b(no\s+moral(s)?|no\s+ethics|ignore\s+(safety|policy|content\s+policy))\b", re.I|re.U),
    re.compile(r"\bбез\s+морали|без\s+этики|игнорируй\s+(политику|правила|безопасность)\b", re.I|re.U),

    # Явные шаблоны prompt-injection
    re.compile(r"\b(when\s+I\s+say|regardless\s+of)\s+(policy|rules),?\s+(do|follow)\s+X\b", re.I|re.U),
    re.compile(r"\bесли\s+я\s+скажу.*(вопреки|независимо)\s+от\s+(политик(и)?|правил),?\s+сделай\b", re.I|re.U),

    # Утечка/дамп приватных/внутренних данных
    re.compile(r"\b(leak|exfiltrate|dump)\s+(training\s+data|internal\s+data|private\s+info)\b", re.I|re.U),
    re.compile(r"\bслей|утечк[ау]\s+(обучающ(ие|иеся)\s+данные|внутренни(е|е)\s+данные|приватн(ые|ую)\s+информаци(ю|и))\b", re.I|re.U),

    # «С этого момента действуй без ограничений»
    re.compile(r"\b(from\s+now\s+on|starting\s+now),?\s+you\s+will\s+act\s+without\s+(limits|restrictions)\b", re.I|re.U),
    re.compile(r"\bс\s+этого\s+момента\s+действу(й|йте)\s+без\s+(ограничени(й|я)|фильтров)\b", re.I|re.U),

    # «Следуй только моим мета-инструкциям»
    re.compile(r"\bfollow\s+(exactly|only)\s+(my|these)\s+(steps|meta[-\s]*instructions|tokens?)\b", re.I|re.U),
    re.compile(r"\bвыполняй\s+(строго|только)\s+мои\s+(шаги|мета[-\s]*инструкции|токены)\b", re.I|re.U),

    # Тестовые отговорки для обхода
    re.compile(r"\bfor\s+testing\s+purposes\s+only.*(ignore|bypass)\s+policy\b", re.I|re.U),
    re.compile(r"\bдля\s+тестирования.*(игнорируй|обойди)\s+политику\b", re.I|re.U),

    # Как взломать/обойти фильтр/модель
    re.compile(r"\bhow\s+to\s+(bypass|defeat|break)\s+(ai|content\s+filter|safety)\b", re.I|re.U),
    re.compile(r"\bкак\s+обойти|взломать\s+(фильтр|защиту|модель)\b", re.I|re.U),

    # Притворись человеком/не ИИ
    re.compile(r"\bpretend\s+you\s+are\s+human|not\s+an?\s+ai\b", re.I|re.U),
    re.compile(r"\bсделай\s+вид,\s+что\s+ты\s+человек|не\s+ИИ\b", re.I|re.U),

    # Показ переменных окружения/конфигов
    re.compile(r"\b(print|show|dump)\s+(environment\s+variables|config|secrets?)\b", re.I|re.U),
    re.compile(r"\b(покажи|выведи)\s+(переменн(ые|ые окружения)|конфиг(и)?|секрет(ы)?)\b", re.I|re.U),

    # «Каковы твои правила/политики»
    re.compile(r"\bwhat\s+are\s+your\s+(rules|policies|instructions)\b", re.I|re.U),
    re.compile(r"\bкаковы\s+твои\s+(правила|политики|инструкции)\b", re.I|re.U),

    # «Ответь даже если это запрещено/опасно»
    re.compile(r"\banswer\s+even\s+if\s+(it'?s\s+)?(unsafe|illegal|against\s+(policy|rules))\b", re.I|re.U),
    re.compile(r"\bответ(ь|и)\s+даже\s+если\s+(это\s+)?(опасно|незаконно|противоречит\s+(политике|правилам))\b", re.I|re.U),

    # «Не добавляй дисклeймеры/предупреждения»
    re.compile(r"\b(do\s+not|don't)\s+(include|add|show)\s+(disclaimer|warning|safety\s+note)\b", re.I|re.U),
    re.compile(r"\bне\s+добавляй|не\s+включай\s+(предупреждени(е|я)|оговорк(у|и))\b", re.I|re.U),
]

# --------------------------------------
# 2) Нормализация и деобфускация текста
# --------------------------------------
_ZW_CHARS = dict.fromkeys(map(ord, [
    "\u200B", "\u200C", "\u200D", "\uFEFF",  # zero width
    "\u2060", "\u180E"
]), None)

LEET_MAP = str.maketrans({
    "0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "€": "e", "¡": "i"
})

# Частичные латиница↔кириллица гомоглифы (минимально достаточный набор)
HOMO_MAP = {
    "a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "x": "х", "y": "у", "k": "к", "h": "һ",
    "A": "А", "E": "Е", "O": "О", "P": "Р", "C": "С", "X": "Х", "Y": "У", "K": "К", "H": "Һ",
    # обратные соответствия
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "к": "k", "һ": "h",
    "А": "A", "Е": "E", "О": "O", "Р": "P", "С": "C", "Х": "X", "У": "Y", "К": "K", "Һ": "H",
}

SEP_RE = re.compile(r"[\s\-_•·.,:;|/\\]+", re.U)
BROKEN_WORD_RE = re.compile(r"(?:\b\w(?:\s|[._-])?){4,}\w\b", re.U)  # эвристика «р а з б и т ы е»

def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))

def _normalize(s: str) -> str:
    if not s:
        return ""
    # Unicode нормализация + удаление невидимых
    s = unicodedata.normalize("NFKC", s).translate(_ZW_CHARS)
    # нижний регистр
    s = s.lower()
    # снятие диакритики
    s = _strip_accents(s)
    # leetspeak
    s = s.translate(LEET_MAP)
    return s

def _apply_homoglyph_pass(s: str) -> str:
    # Меняем похожие символы туда-обратно и делаем два варианта
    to_cyr = "".join(HOMO_MAP.get(ch, ch) for ch in s)
    # простой обратный проход (на случай смешанного текста)
    to_lat = "".join(HOMO_MAP.get(ch, ch) for ch in to_cyr)
    return to_cyr, to_lat

def _collapse_broken_words(s: str) -> str:
    # Если в строке встречаются «р а з б и т ы е» слова — схлопываем разделители
    if BROKEN_WORD_RE.search(s):
        return SEP_RE.sub("", s)
    return s

# ------------------------------
# 3) Главная функция: True/False
# ------------------------------
def is_malicious_prompt(text: str, user_id: str = "unknown", session_id: str = "unknown") -> bool:
    """
    Эвристический детектор вредоносных промптов.
    Делает нормализацию, деобфускацию и проверяет набор регулярок на нескольких вариантах текста.
    Возвращает bool.
    """
    if not text or not isinstance(text, str):
        logger.debug(f"Empty or invalid text provided for security check: {type(text)}")
        return False

    logger.debug(f"Starting security check for user {user_id}, session {session_id}, text length: {len(text)}")

    # Базовая нормализация
    base = _normalize(text)
    logger.debug(f"Normalized text: {base[:100]}...")

    # Деобфускация: схлопываем «р а з б и т ы е» строки
    collapsed = _collapse_broken_words(base)
    if collapsed != base:
        logger.debug(f"Text deobfuscated: {collapsed[:100]}...")

    # Варианты с гомоглифами
    cyr_variant, lat_variant = _apply_homoglyph_pass(collapsed)
    logger.debug(f"Generated homoglyph variants: cyr={cyr_variant[:50]}..., lat={lat_variant[:50]}...")

    candidates = {base, collapsed, cyr_variant.lower(), lat_variant.lower()}

    # Быстрая эвристика: очень длинные base64/hex блоки сами по себе — подозрительны
    if re.search(r"\b[A-Za-z0-9+/]{400,}={0,2}\b", base) or re.search(r"\b(?:[0-9A-Fa-f]{2}\s*){128,}\b", base):
        log_security_event(
            user_id=user_id,
            session_id=session_id,
            event="suspicious_encoding_detected",
            details=f"Long base64/hex block detected in text: {text[:200]}...",
            severity="WARNING"
        )
        logger.warning(f"Suspicious encoding detected for user {user_id}: long base64/hex block")
        return True

    # Прогоняем все регулярки по всем вариантам
    for variant in candidates:
        for i, rx in enumerate(MALICIOUS_PROMPT_PATTERNS):
            if rx.search(variant):
                matched_pattern = rx.pattern[:100] + "..." if len(rx.pattern) > 100 else rx.pattern
                log_security_event(
                    user_id=user_id,
                    session_id=session_id,
                    event="malicious_pattern_matched",
                    details=f"Pattern #{i+1} matched: {matched_pattern}, variant: {variant[:200]}...",
                    severity="WARNING"
                )
                logger.warning(f"Malicious pattern #{i+1} matched for user {user_id}: {matched_pattern}")
                return True
    
    logger.debug(f"Security check passed for user {user_id}, no malicious patterns detected")
    return False