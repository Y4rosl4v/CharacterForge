# Лабораторная работа 4: Реализация функций редактирования и работы с изображениями
### Функции редактирования
- Маршрут /characters/int:character_id/edit для редактирования персонажей
- AI-редактирование через маршрут /characters/int:character_id/ai_edit
- Реализация функции edit_character_with_ai
### Генерация изображений
- Интеграция с API для генерации изображений (pollinations.ai)
- Функции generate_character_image() и build_anime_image_prompt()
- Обработка ошибок и создание заглушек

### Добавленные файлы и изменения
1. app.py - фрагменты:
  - Маршрут /characters/int:character_id/edit и его реализация
  - Новый маршрут /characters/int:character_id/ai_edit
  - Функции generate_character_image() и build_anime_image_prompt()
  - Функции create_placeholder_image() и create_error_image()
2. generator.py - функция edit_character_with_ai
3. templates/result.html - отображение персонажа с кнопками редактирования
