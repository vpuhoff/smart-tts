from __future__ import annotations

import re

import inflect


class TextNormalizer:
    _MONEY_PATTERN = re.compile(r"\$(\d+(?:\.\d{2})?)")
    _PHONE_PATTERN = re.compile(r"\b(\d{3})-(\d{3})-(\d{4})\b")
    _DATE_PATTERN = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")

    def __init__(self) -> None:
        self._engine = inflect.engine()

    def normalize(self, text: str, language: str | None) -> str:
        if language and not language.lower().startswith("en"):
            return text
        normalized = self._normalize_money(text)
        normalized = self._normalize_phones(normalized)
        normalized = self._normalize_dates(normalized)
        return normalized

    def _normalize_money(self, text: str) -> str:
        def repl(match: re.Match[str]) -> str:
            amount = match.group(1)
            if "." in amount:
                dollars, cents = amount.split(".", 1)
                dollars_words = self._number_to_words(int(dollars))
                cents_words = self._number_to_words(int(cents))
                return f"{dollars_words} dollars and {cents_words} cents"
            return f"{self._number_to_words(int(amount))} dollars"

        return self._MONEY_PATTERN.sub(repl, text)

    def _normalize_phones(self, text: str) -> str:
        def repl(match: re.Match[str]) -> str:
            parts = [self._digit_word(d) for d in match.group(0).replace("-", "")]
            return " ".join(parts)

        return self._PHONE_PATTERN.sub(repl, text)

    def _normalize_dates(self, text: str) -> str:
        def repl(match: re.Match[str]) -> str:
            month, day, year = match.groups()
            month_name = self._month_name(int(month))
            day_words = self._ordinal(int(day))
            year_words = self._year_to_words(year)
            return f"{month_name} {day_words}, {year_words}"

        return self._DATE_PATTERN.sub(repl, text)

    def _number_to_words(self, value: int) -> str:
        return self._engine.number_to_words(value)

    def _ordinal(self, value: int) -> str:
        return self._engine.ordinal(value)

    def _month_name(self, month: int) -> str:
        months = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        if 1 <= month <= 12:
            return months[month - 1]
        return str(month)

    def _year_to_words(self, year: str) -> str:
        if len(year) == 2:
            return self._number_to_words(int(year))
        if len(year) == 4:
            return self._number_to_words(int(year))
        return year

    @staticmethod
    def _digit_word(digit: str) -> str:
        mapping = {
            "0": "zero",
            "1": "one",
            "2": "two",
            "3": "three",
            "4": "four",
            "5": "five",
            "6": "six",
            "7": "seven",
            "8": "eight",
            "9": "nine",
        }
        return mapping.get(digit, digit)
