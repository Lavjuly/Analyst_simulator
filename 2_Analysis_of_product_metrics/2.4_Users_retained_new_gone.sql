-- Построить график, график, который позволяет взглянуть на активную аудиторию с точки зрения новых, старых и ушедших пользователей.
-- На графике мы отобразим активную аудиторию по неделям, для каждой недели выделим три типа пользователей.
-- Новые — первая активность в ленте была на этой неделе.
-- Старые — активность была и на этой и на прошлой неделе.
-- Ушедшие — активность была на прошлой неделе, на этой не было.

SELECT this_week, previous_week, -uniq(user_id) as num_users, status FROM
(SELECT user_id, 
groupUniqArray(toMonday(toDate(time))) as weeks_visited, 
addWeeks(arrayJoin(weeks_visited), +1) this_week, 
if(has(weeks_visited, this_week) = 1, 'retained', 'gone') as status, 
addWeeks(this_week, -1) as previous_week
FROM simulator.feed_actions
group by user_id)

where status = 'gone'
group by this_week, previous_week, status
HAVING this_week != addWeeks(toMonday(today()), +1)

union all

SELECT this_week, previous_week, toInt64(uniq(user_id)) as num_users, status FROM
(SELECT user_id, 
groupUniqArray(toMonday(toDate(time))) as weeks_visited, 
arrayJoin(weeks_visited) this_week, 
if(has(weeks_visited, addWeeks(this_week, -1)) = 1, 'retained', 'new') as status, 
addWeeks(this_week, -1) as previous_week
FROM simulator.feed_actions
group by user_id)

group by this_week, previous_week, status