-- В наших данных использования ленты новостей есть два типа юзеров: те, кто пришел через платный трафик source = 'ads', и те, кто пришел через органические каналы source = 'organic'.
-- Ваша задача — проанализировать и сравнить Retention этих двух групп пользователей.
-- Находим Retention для пользователей, пришедших через органические каналы:

SELECT toString(start_day) start_day,
       toString(day) day,
       count(user_id) AS users
FROM
  (SELECT *
   FROM
     (SELECT user_id,
             min(toDate(time)) AS start_day
      FROM simulator_20230720.feed_actions
      WHERE source = 'organic'
      GROUP BY user_id) t1
   JOIN
     (SELECT DISTINCT user_id, toDate(time) AS day
      FROM simulator_20230720.feed_actions
      WHERE source = 'organic') t2 USING user_id
   WHERE start_day >= today() - 20 )
GROUP BY start_day,
         day

       