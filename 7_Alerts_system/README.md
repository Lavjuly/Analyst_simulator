# 7. Поиск аномалий (система алертов)

## Задание:
Напишите систему алертов для нашего приложения
Система должна с периодичность каждые 15 минут проверять ключевые метрики, такие как активные пользователи в ленте / мессенджере, просмотры, лайки, CTR, количество отправленных сообщений. 

Изучите поведение метрик и подберите наиболее подходящий метод для детектирования аномалий. На практике как правило применяются статистические методы. 
В самом простом случае можно, например, проверять отклонение значения метрики в текущую 15-минутку от значения в такую же 15-минутку день назад. 

В случае обнаружения аномального значения, в чат должен отправиться алерт - сообщение со следующей информацией: метрика, ее значение, величина отклонения.
В сообщение можно добавить дополнительную информацию, которая поможет при исследовании причин возникновения аномалии, это может быть, например,  график, ссылки на дашборд/чарт в BI системе.

## Что сделали:
Написали код в Python с системой алертов по приложению. С помощью телеграм-бота и Airflow запустили отправку информации в наш чат, при возникновении отклонения ключевых метрик.