# Лабораторная работа 5: Реализация экспорта данных и финальная доработка
### Функции экспорта
- Экспорт в TXT формат через маршрут /characters/int:character_id/export/txt
- Экспорт в PDF формат через маршрут /characters/int:character_id/export/pdf
- Форматирование текста функцией character_to_text()
### Дополнительные функции
- Удаление персонажей /characters/int:character_id/delete
- Обновление изображений /characters/int:character_id/regenerate-image
### Тестирование всего функционала и исправление ошибок

### Добавленные файлы и изменения
1. app.py - фрагменты:
   - Функция character_to_text() для форматирования данных
   - Маршрут /characters/int:character_id/export/txt
   - Маршрут /characters/int:character_id/export/pdf с формированием PDF
   - Функции получения путей к файлам экспорта
2. templates/result.html - кнопки экспорта
3. static/style.css - стили для элементов интерфейса
