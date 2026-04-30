"""
Utilitário de parsing de datas — tolerante a qualquer formato que um hóspede brasileiro use.

Formatos suportados:
  Numérico:
    01/05         → 01 de maio do ano corrente
    01/05/2025    → 01 de maio de 2025
    01/05/25      → 01 de maio de 2025
    2025-05-01    → ISO 8601
    01.05.2025    → separador ponto
    01-05-2025    → separador hífen
    01 05 2025    → separador espaço

  Por extenso (PT-BR):
    1 de maio         → 01/05/ano_corrente
    dia 1 de maio     → 01/05/ano_corrente
    primeiro de maio  → 01/05/ano_corrente
    primeiro de maio de 2025
    maio/2025 (sem dia → assume dia 1)

  Relativos:
    hoje              → data atual
    amanhã / amanha   → data atual + 1 dia
    depois de amanhã  → data atual + 2 dias
    próxima semana    → data atual + 7 dias
    semana que vem    → data atual + 7 dias
    fim de semana     → próximo sábado
    próximo fds       → próximo sábado

  Extração de múltiplas datas de um texto livre:
    "do dia 10 ao dia 12 de maio"
    "de 01/05 até 05/05"
    "entre 10 e 12/05"
    "check-in 01/05 checkout 02/05"
"""
import re
import logging
from datetime import date, datetime, timedelta
from typing import Optional, Tuple, List

logger = logging.getLogger("DATE_PARSER")

# Mapeamento de meses por extenso → número
MONTH_MAP = {
    "janeiro": 1, "jan": 1,
    "fevereiro": 2, "fev": 2,
    "março": 3, "marco": 3, "mar": 3,
    "abril": 4, "abr": 4,
    "maio": 5, "mai": 5,
    "junho": 6, "jun": 6,
    "julho": 7, "jul": 7,
    "agosto": 8, "ago": 8,
    "setembro": 9, "set": 9,
    "outubro": 10, "out": 10,
    "novembro": 11, "nov": 11,
    "dezembro": 12, "dez": 12,
}

# Mapeamento de ordinais por extenso → número
ORDINAL_MAP = {
    "primeiro": 1, "um": 1, "uma": 1,
    "dois": 2, "duas": 2, "segundo": 2,
    "três": 3, "tres": 3, "terceiro": 3,
    "quatro": 4, "quarta": 4,
    "cinco": 5, "quinta": 5,
    "seis": 6, "sexta": 6,
    "sete": 7, "sétimo": 7, "setimo": 7,
    "oito": 8, "oitavo": 8,
    "nove": 9, "nono": 9,
    "dez": 10, "décimo": 10, "decimo": 10,
}


def _current_year() -> int:
    return datetime.now().year


def _fix_year(y: int) -> int:
    """Converte ano de 2 dígitos para 4 dígitos."""
    if y < 100:
        return 2000 + y
    return y


def _safe_date(d: int, m: int, y: int) -> Optional[date]:
    """Cria um objeto date com validação silenciosa."""
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_date(value) -> Optional[date]:
    """
    Converte qualquer representação de data para um objeto date.

    Args:
        value: str, date, datetime, ou None

    Returns:
        date | None se não conseguiu parsear
    """
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip().lower()
    if not text:
        return None

    today = date.today()

    # --- RELATIVOS ---
    if text in ("hoje", "today"):
        return today
    if text in ("amanhã", "amanha", "tomorrow"):
        return today + timedelta(days=1)
    if text in ("depois de amanhã", "depois de amanha", "after tomorrow"):
        return today + timedelta(days=2)
    if "próxima semana" in text or "proxima semana" in text or "semana que vem" in text:
        return today + timedelta(days=7)
    if "fim de semana" in text or "fds" in text or "próximo fds" in text:
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        return today + timedelta(days=days_until_saturday)

    # --- NUMÉRICO COM SEPARADORES (/ . - espaço) ---
    # Tenta os formatos mais comuns primeiro
    numeric_patterns = [
        # DD/MM/YYYY ou DD/MM/YY
        (r'^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})$', lambda m: _safe_date(int(m.group(1)), int(m.group(2)), _fix_year(int(m.group(3))))),
        # YYYY-MM-DD (ISO)
        (r'^(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})$', lambda m: _safe_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))),
        # DD/MM (sem ano → ano corrente)
        (r'^(\d{1,2})[/\-\.](\d{1,2})$', lambda m: _safe_date(int(m.group(1)), int(m.group(2)), _current_year())),
        # DD MM YYYY (com espaços)
        (r'^(\d{1,2})\s+(\d{1,2})\s+(\d{4})$', lambda m: _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
    ]
    for pattern, builder in numeric_patterns:
        m = re.match(pattern, text)
        if m:
            result = builder(m)
            if result:
                return result

    # --- POR EXTENSO (ex: "1 de maio", "primeiro de maio de 2025") ---
    # Substitui ordinais por números
    normalized = text
    for word, num in ORDINAL_MAP.items():
        normalized = re.sub(rf'\b{word}\b', str(num), normalized)

    # "dia 10 de maio" ou "10 de maio" ou "10 maio"
    for month_name, month_num in MONTH_MAP.items():
        pattern = rf'(\d{{1,2}})\s+(?:de\s+)?{month_name}(?:\s+(?:de\s+)?(\d{{2,4}}))?'
        m = re.search(pattern, normalized)
        if m:
            day = int(m.group(1))
            year = _fix_year(int(m.group(2))) if m.group(2) else _current_year()
            result = _safe_date(day, month_num, year)
            if result:
                return result

    # "maio/2025" ou "maio de 2025" (sem dia específico → assume dia 1)
    for month_name, month_num in MONTH_MAP.items():
        pattern = rf'\b{month_name}(?:[/\s]+(?:de\s+)?(\d{{4}}))?\b'
        m = re.search(pattern, normalized)
        if m:
            year = int(m.group(1)) if m.group(1) else _current_year()
            result = _safe_date(1, month_num, year)
            if result:
                return result

    logger.debug(f"[DATE_PARSER] Não conseguiu parsear: '{value}'")
    return None


def extract_dates_from_text(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrai check_in e check_out de um texto livre em linguagem natural.

    Retorna as datas já normalizadas no formato 'DD/MM/YYYY' para consistência.
    Retorna (check_in, check_out) como strings, ou None se não encontrou.
    """
    text_lower = text.lower()
    today = date.today()
    found_dates: List[date] = []

    # --- Padrão 0: relativos com range ("de amanhã até depois de amanhã") ---
    relative_map = {
        "hoje": today,
        "amanhã": today + timedelta(days=1),
        "amanha": today + timedelta(days=1),
        "depois de amanhã": today + timedelta(days=2),
        "depois de amanha": today + timedelta(days=2),
    }
    relative_range = re.search(
        r'(?:de|do|from|a partir de)?\s*(amanhã|amanha|hoje|depois de amanhã|depois de amanha)'
        r'\s+(?:até|ate|ao|a\b|–|-)\s*(amanhã|amanha|hoje|depois de amanhã|depois de amanha)',
        text_lower
    )
    if relative_range:
        d1 = relative_map.get(relative_range.group(1).strip())
        d2 = relative_map.get(relative_range.group(2).strip())
        if d1 and d2:
            return _fmt(min(d1, d2)), _fmt(max(d1, d2))

    # --- Padrão 1: "de [data] até/a/ao [data]" ---
    range_pattern = re.search(
        r'(?:de|do|from)?\s*(.+?)\s+(?:até|ate|ao dia|ao|a\b|–|-)\s*(.+?)(?:\s*[,\.;]|\s*$)',
        text_lower
    )
    if range_pattern:
        d1 = parse_date(range_pattern.group(1).strip())
        d2 = parse_date(range_pattern.group(2).strip())
        if d1 and d2 and d1 != d2:
            return _fmt(min(d1, d2)), _fmt(max(d1, d2))

    # --- Padrão 2: "entre [data] e [data]" ---
    # Suporta: "entre 15 e 17/07", "entre 01/05 e 03/05"
    between_pattern = re.search(
        r'entre\s+(\d{1,2}[/\-\.]?\d{0,2}[/\-\.]?\d{0,4}|\d{1,2})\s+e\s+(\d{1,2}[/\-\.]\d{1,2}(?:[/\-\.]\d{2,4})?)',
        text_lower
    )
    if between_pattern:
        raw1 = between_pattern.group(1).strip()
        raw2 = between_pattern.group(2).strip()
        # Se o primeiro número não tem separador, assume mesmo mês do segundo
        if re.match(r'^\d{1,2}$', raw1) and '/' in raw2:
            month_part = '/'.join(raw2.split('/')[1:])  # pega MM ou MM/YYYY
            raw1 = f"{raw1}/{month_part}"
        d1 = parse_date(raw1)
        d2 = parse_date(raw2)
        if d1 and d2:
            return _fmt(min(d1, d2)), _fmt(max(d1, d2))

    # --- Padrão 3: "do dia X ao dia Y de [mês]" ---
    # "do dia 20 ao dia 22 de agosto"
    for month_name, month_num in MONTH_MAP.items():
        m = re.search(
            rf'(?:do\s+)?dia\s+(\d{{1,2}})\s+(?:ao|a|até)\s+(?:o\s+)?(?:dia\s+)?(\d{{1,2}})\s+(?:de\s+)?{month_name}(?:\s+(?:de\s+)?(\d{{4}}))?',
            text_lower
        )
        if m:
            year = int(m.group(3)) if m.group(3) else _current_year()
            d1 = _safe_date(int(m.group(1)), month_num, year)
            d2 = _safe_date(int(m.group(2)), month_num, year)
            if d1 and d2:
                return _fmt(min(d1, d2)), _fmt(max(d1, d2))

    # --- Padrão 4: datas numéricas no texto ---
    numeric_dates_raw = re.findall(
        r'\b(\d{1,2}[/\-\.]\d{1,2}(?:[/\-\.]\d{2,4})?|\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})\b',
        text
    )
    for raw in numeric_dates_raw:
        d = parse_date(raw)
        if d:
            found_dates.append(d)

    # --- Padrão 5: datas por extenso no texto ---
    for month_name, month_num in MONTH_MAP.items():
        matches = re.finditer(
            rf'(\d{{1,2}}|primeiro|um|dois|três|tres|quatro|cinco|seis|sete|oito|nove|dez)\s+(?:de\s+)?{month_name}(?:\s+(?:de\s+)?(\d{{2,4}}))?',
            text_lower
        )
        for m in matches:
            day_raw = m.group(1)
            day = ORDINAL_MAP.get(day_raw, None) or (int(day_raw) if day_raw.isdigit() else None)
            if not day:
                continue
            year = _fix_year(int(m.group(2))) if m.group(2) else _current_year()
            d = _safe_date(day, month_num, year)
            if d and d not in found_dates:
                found_dates.append(d)

    # --- Padrão 6: relativos soltos ---
    if "amanhã" in text_lower or "amanha" in text_lower:
        found_dates.append(today + timedelta(days=1))
    if "hoje" in text_lower and not found_dates:
        found_dates.append(today)

    # Remove duplicatas e ordena
    found_dates = sorted(set(found_dates))

    if len(found_dates) >= 2:
        return _fmt(found_dates[0]), _fmt(found_dates[1])
    elif len(found_dates) == 1:
        return _fmt(found_dates[0]), None

    return None, None


def _fmt(d: date) -> str:
    """Formata para DD/MM/YYYY (padrão interno do sistema)."""
    return d.strftime("%d/%m/%Y")


def extract_group_size_from_text(text: str) -> Optional[int]:
    """
    Extrai número de pessoas de um texto livre.

    Suporta:
      "2 pessoas", "para 3", "somos 4", "2 adultos", "família de 3",
      "casal" → 2, "sozinho" → 1, "individual" → 1
    """
    text_lower = text.lower()

    # Casos textuais
    if any(w in text_lower for w in ["casal", "dois", "duas pessoas", "para dois"]):
        return 2
    if any(w in text_lower for w in ["sozinho", "sozinha", "individual", "só eu", "so eu", "uma pessoa"]):
        return 1
    if "família" in text_lower or "familia" in text_lower:
        # Tenta capturar "família de 4"
        m = re.search(r'famil[iíi]a\s+de\s+(\d+)', text_lower)
        if m:
            return int(m.group(1))

    # Numérico: "3 pessoas", "para 4 hóspedes", "somos 2", "2 adultos"
    patterns = [
        r'(\d+)\s*(?:pessoa|hóspede|hospede|adulto|pax|pessoa)',
        r'(?:para|somos|seremos|serão|virão|vem)\s+(\d+)',
        r'(?:grupo de|turma de|família de)\s+(\d+)',
        r'^(\d+)$',  # número sozinho
    ]
    for pattern in patterns:
        m = re.search(pattern, text_lower)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 20:  # sanidade: máximo razoável
                return n

    return None
