import json
import os
import random
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


AI_API_URL = "https://gen.pollinations.ai/v1/chat/completions"


def extract_json(text):
    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("AI не вернул JSON.")

    return text[start:end + 1]


def clamp_stat(value):
    try:
        value = int(value)
    except Exception:
        value = random.randint(3, 8)

    return max(1, min(10, value))


def validate_character(data, prompt):
    required_fields = [
        "name",
        "character_class",
        "race",
        "strength",
        "intelligence",
        "agility",
        "magic",
        "description",
        "goal",
        "abilities",
        "image_prompt"
    ]

    for field in required_fields:
        if field not in data:
            raise ValueError(f"AI не вернул поле: {field}")

    abilities = data["abilities"]

    if isinstance(abilities, list):
        abilities = ", ".join(str(item) for item in abilities)

    return {
        "name": str(data["name"]).strip(),
        "character_class": str(data["character_class"]).strip(),
        "race": str(data["race"]).strip(),
        "strength": clamp_stat(data["strength"]),
        "intelligence": clamp_stat(data["intelligence"]),
        "agility": clamp_stat(data["agility"]),
        "magic": clamp_stat(data["magic"]),
        "description": str(data["description"]).strip(),
        "goal": str(data["goal"]).strip(),
        "abilities": str(abilities).strip(),
        "image_prompt": str(data["image_prompt"]).strip(),
        "source_prompt": prompt
    }


def generate_character(prompt, used_races=None, used_classes=None, used_names=None):
    used_races = used_races or []
    used_classes = used_classes or []
    used_names = used_names or []

    random_seed = random.randint(1, 999999999)

    system_prompt = """
Ты генератор игровых RPG-персонажей.

Твоя задача — создать уникального игрового персонажа на основе текстового описания пользователя.

Важно:
- НЕ выбирай персонажа из заранее заданных классов.
- НЕ ограничивайся стандартными архетипами вроде маг, воин, лучник, эльф.
- Если пользователь описывает нестандартное существо, придумай новую расу и новый класс.
- Если пользователь просит трансформера-собаку с лазерами из глаз, создай именно такого персонажа, а не мага или воина.
- Учитывай смысл запроса, а не отдельные ключевые слова.
- Каждый результат должен быть новым и отличаться от предыдущих.

Верни строго JSON без пояснений, без markdown и без ```.

Формат JSON:
{
  "name": "уникальное имя персонажа",
  "character_class": "уникальный класс персонажа",
  "race": "раса или тип существа",
  "strength": число от 1 до 10,
  "intelligence": число от 1 до 10,
  "agility": число от 1 до 10,
  "magic": число от 1 до 10,
  "description": "краткое, но выразительное описание персонажа",
  "goal": "цель персонажа",
  "abilities": "способности через запятую",
  "image_prompt": "английский prompt для anime fantasy/sci-fi RPG character art"
}

Правила:
1. Имя должно быть новым, необычным и подходить персонажу.
2. Раса должна соответствовать запросу пользователя.
3. Класс должен соответствовать запросу пользователя.
4. Характеристики должны быть логичными.
5. Если персонаж технологический, параметр magic может быть низким, а интеллект/ловкость/сила выше.
6. Если персонаж магический, magic должен быть выше.
7. image_prompt должен быть на английском языке.
8. image_prompt должен описывать красивую anime-style иллюстрацию персонажа в полный рост.
9. В image_prompt обязательно добавь: no text, no logo, no watermark.
10. Не повторяй уже использованные имена.
11. По возможности не повторяй уже использованные расы и классы.
"""

    user_prompt = f"""
Запрос пользователя:
{prompt}

Уже использованные имена:
{used_names}

Уже использованные расы:
{used_races}

Уже использованные классы:
{used_classes}

Случайный seed для уникальности:
{random_seed}

Создай нового уникального персонажа.
"""

    payload = {
        "model": "openai",
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "temperature": 1.15,
        "max_tokens": 900
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "CharacterForgeStudentProject/1.0"
    }

    api_key = os.getenv("POLLINATIONS_API_KEY")

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = Request(
        AI_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urlopen(request, timeout=45) as response:
            raw_response = response.read().decode("utf-8")

        response_data = json.loads(raw_response)
        content = response_data["choices"][0]["message"]["content"]

        json_text = extract_json(content)
        character_data = json.loads(json_text)

        return validate_character(character_data, prompt)

    except HTTPError as error:
        raise RuntimeError(f"AI-сервис вернул ошибку HTTP {error.code}: {error.reason}")

    except URLError as error:
        raise RuntimeError(f"Ошибка сети при обращении к AI-сервису: {error.reason}")

    except Exception as error:
        raise RuntimeError(f"Не удалось сгенерировать персонажа через AI: {error}")


# ========== НОВАЯ ФУНКЦИЯ ДЛЯ AI-РЕДАКТИРОВАНИЯ ==========

def edit_character_with_ai(current_character, user_instruction):
    """
    Редактирует существующего персонажа по запросу пользователя.
    
    Параметры:
    - current_character: dict с полями name, character_class, race,
                         strength, intelligence, agility, magic,
                         description, goal, abilities, image_prompt
    - user_instruction: строка, что именно изменить
    
    Возвращает: dict с обновлёнными полями (только те, что изменились)
    """
    # Подготавливаем текущие данные для AI
    current_description = f"""
Текущий персонаж:
- Имя: {current_character['name']}
- Класс: {current_character['character_class']}
- Раса: {current_character['race']}
- Сила: {current_character['strength']}
- Интеллект: {current_character['intelligence']}
- Ловкость: {current_character['agility']}
- Магия: {current_character['magic']}
- Описание: {current_character['description']}
- Цель: {current_character['goal']}
- Способности: {current_character['abilities']}
- Prompt для картинки: {current_character.get('image_prompt', '')}
"""

    system_prompt_edit = """
Ты редактор RPG-персонажа. Пользователь хочет изменить некоторые поля существующего персонажа.
Верни ТОЛЬКО JSON с теми полями, которые нужно обновить. Не меняй остальные поля.
Формат ответа:
{
  "name": "новое имя (если нужно)",
  "character_class": "новый класс (если нужно)",
  "race": "новая раса (если нужно)",
  "strength": число от 1 до 10,
  "intelligence": число от 1 до 10,
  "agility": число от 1 до 10,
  "magic": число от 1 до 10,
  "description": "новое описание",
  "goal": "новая цель",
  "abilities": "новые способности через запятую",
  "image_prompt": "новый промпт для картинки"
}

Правила:
- Если поле не меняется — НЕ включай его в JSON.
- Характеристики должны оставаться логичными относительно класса и расы.
- Если просят изменить только имя — верни { "name": "новое имя" }.
- Если просят "сделать сильнее" — увеличь strength, но не более 10.
- Если просят "сделать магичнее" — увеличь magic.
- Не добавляй лишних объяснений, только JSON.
"""

    user_prompt_edit = f"""
{current_description}

Запрос пользователя на изменение:
{user_instruction}

Верни JSON только с изменяемыми полями.
"""

    payload = {
        "model": "openai",
        "messages": [
            {"role": "system", "content": system_prompt_edit},
            {"role": "user", "content": user_prompt_edit}
        ],
        "temperature": 1.0,
        "max_tokens": 700
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "CharacterForgeStudentProject/1.0"
    }
    api_key = os.getenv("POLLINATIONS_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = Request(
        AI_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urlopen(request, timeout=45) as response:
            raw_response = response.read().decode("utf-8")
        response_data = json.loads(raw_response)
        content = response_data["choices"][0]["message"]["content"]
        json_text = extract_json(content)
        updates = json.loads(json_text)

        # Применяем обновления к текущему персонажу
        edited = current_character.copy()
        for key, value in updates.items():
            if key in ["strength", "intelligence", "agility", "magic"]:
                edited[key] = clamp_stat(value)
            else:
                edited[key] = str(value).strip()
        return edited

    except Exception as e:
        raise RuntimeError(f"Ошибка при редактировании персонажа: {e}")