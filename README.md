# ЛМ-ПИОТ Мониторинг

Мониторинг статуса серверов ЛМЧЗ, Контроллер ЛМ и ПИОТ

## Возможности

- Мониторинг трех сервисов: ЛМЧЗ, Контроллер ЛМ, ПИОТ
- Отображение статуса лицензии ПИОТ
- Импорт/экспорт данных в JSON/CSV
- Docker поддержка

## Запуск

```bash
# Клонирование
git clone https://github.com/lind1745/lm-piot-monitor.git
cd lm-piot-monitor

# Запуск через Docker
docker-compose up -d

# Или напрямую
pip install -r requirements.txt
python app.py


Открыть: http://localhost:5000