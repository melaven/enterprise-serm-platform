import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Инициализация сервера
mcp = FastMCP("FrontendCleaner")

FRONTEND_DIR = Path("frontend/src")


@mcp.tool()
def scan_frontend_components(keywords: list[str]) -> dict:
    """
    Сканирует TSX/TS файлы фронтенда на наличие указанных ключевых слов
    (например, ['AI', 'ИИ', 'ai_pending', 'Черновик']).
    Возвращает словарь с путями к файлам и номерами строк.
    """
    if not FRONTEND_DIR.exists():
        return {"error": f"Директория {FRONTEND_DIR.absolute()} не найдена"}

    matches = {}
    for filepath in FRONTEND_DIR.rglob("*.*"):
        if filepath.suffix not in [".tsx", ".ts"]:
            continue

        try:
            content = filepath.read_text(encoding="utf-8")
            lines = content.split("\n")

            file_matches = []
            for i, line in enumerate(lines):
                # Ищем точное вхождение без учета регистра
                for kw in keywords:
                    if (
                        re.search(r"\b" + re.escape(kw) + r"\b", line, re.IGNORECASE)
                        or kw.lower() in line.lower()
                    ):
                        file_matches.append({"line_num": i + 1, "text": line.strip()})
                        break  # Избегаем дублей, если в строке несколько ключей

            if file_matches:
                matches[str(filepath)] = file_matches
        except Exception:
            continue

    return matches


@mcp.tool()
def remove_jsx_lines(filepath: str, lines_to_delete: list[int]) -> str:
    """
    Хирургически удаляет конкретные строки из файла.
    Использовать для вырезания карточек, бейджей или колонок.
    """
    path = Path(filepath)
    if not path.exists():
        return f"Ошибка: Файл {filepath} не найден"

    content = path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Удаляем с конца, чтобы не сбить индексы при сдвиге
    for i in sorted(lines_to_delete, reverse=True):
        idx = i - 1
        if 0 <= idx < len(lines):
            del lines[idx]

    path.write_text("\n".join(lines), encoding="utf-8")
    return f"Успешно вырезано {len(lines_to_delete)} строк из {path.name}. Обязательно проверь закрывающие теги (</div>, </>)."


if __name__ == "__main__":
    mcp.run()
