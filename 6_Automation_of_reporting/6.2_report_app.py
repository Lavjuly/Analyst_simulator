# Импортируем необходимые библиотеки
import telegram
import matplotlib.pyplot as plt
import seaborn as sns
import io
import os
from datetime import datetime, date, timedelta
import pandas as pd
import pandahouse as ph
from airflow.decorators import dag, task
from airflow.operators.python import get_current_context

# Подключаемся к БД
connection = {'host': 'https://clickhouse.lab.karpov.courses',
                      'database':'simulator_20230720',
                      'user':'student', 
                      'password':'dpo_python_2020'}

# спрятали токен бота
from dotenv import load_dotenv
load_dotenv()
bot = telegram.Bot(token=os.environ.get("REPORT_BOT_TOKEN")) # получаем доступ
chat_id = -927780322


# Дефолтные параметры, которые прокидываются в таски
default_args = {
    'owner': 'j-lavrenteva',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2023, 8, 26),
}

# Интервал запуска DAG (ежедневно в 11:00)
schedule_interval = '0 11 * * *'

yd = date.today() - timedelta(days=1)
start_date = date.today() - timedelta(days=7)
end_date = date.today() - timedelta(days=1)


@dag(default_args=default_args, schedule_interval=schedule_interval, catchup=False)
def j_lavrenteva_add_report():
    
    @task
    def dau_metrics():
        # Запрос для общего DAU за неделю и в разрезе платформ
        query_1 = """
        SELECT date, uniqExact(user_id) AS total_DAU, uniqExactIf(user_id, os='iOS') AS users_ios, 
        uniqExactIf(user_id, os='Android') AS users_android
        FROM (
            SELECT toDate(time) AS date, user_id, os
            FROM simulator_20230720.feed_actions
            UNION ALL
            SELECT toDate(time) AS date, user_id, os
            FROM simulator_20230720.message_actions
        ) AS merged
        WHERE date BETWEEN toDate(now()) - 7 AND toDate(now()) - 1
        GROUP BY date
        """    
        dau = ph.read_clickhouse(query_1, connection=connection)
        return dau

    @task
    def actions_metrics():
        query_2 = """
        SELECT date, likes, views, CTR, messages 
        FROM (
            SELECT toDate(time) AS date,  countIf(action='like') AS likes, countIf(action='view') AS views,
            ROUND(countIf(action='like')/countIf(action='view'), 2) AS CTR
            FROM simulator_20230720.feed_actions
            WHERE date BETWEEN toDate(now()) - 7 AND toDate(now()) - 1
            GROUP BY toDate(time)) AS t1
            INNER JOIN
            (SELECT toDate(time) AS date, COUNT(user_id) AS messages
            FROM simulator_20230720.message_actions
            WHERE date BETWEEN toDate(now()) - 7 AND toDate(now()) - 1
            GROUP BY toDate(time)) AS t2 ON t1.date = t2.date
        """
        actions = ph.read_clickhouse(query_2, connection=connection)
        return actions
        

    @task
    def total_add_metrics(dau, actions):
        # Вычисляем процентное изменение для каждой метрики за день назад
        dau_percent_change = dau.loc[6, 'total_DAU'] / dau.loc[5, 'total_DAU'] - 1
        users_ios_percent_change = dau.loc[6, 'users_ios'] / dau.loc[5, 'users_ios'] - 1
        users_android_percent_change = dau.loc[6, 'users_android'] / dau.loc[5, 'users_android'] - 1
        likes_percent_change = actions.loc[6, 'likes'] / actions.loc[5, 'likes'] - 1
        views_percent_change = actions.loc[6, 'views'] / actions.loc[5, 'views'] - 1
        ctr_percent_change = actions.loc[6, 'CTR'] / actions.loc[5, 'CTR'] - 1
        msg = f"Ключевые метрики по приложению на {yd.strftime('%d-%m-%Y')}:\n\n" \
              f"Общее DAU = {dau.loc[6, 'total_DAU']} ({dau_percent_change:.2%} изменение относительно 1 дня назад)\n" \
              f"Пользователи iOS = {dau.loc[6, 'users_ios']} ({users_ios_percent_change:.2%} изменение относительно 1 дня назад)\n" \
              f"Пользователи Android = {dau.loc[6, 'users_android']} ({users_android_percent_change:.2%} изменение относительно 1 дня назад)\n" \
              f"likes = {actions.loc[6, 'likes']} ({likes_percent_change:.2%} изменение относительно 1 дня назад)\n" \
              f"views = {actions.loc[6, 'views']} ({views_percent_change:.2%} изменение относительно 1 дня назад)\n" \
              f"CTR = {actions.loc[6, 'CTR']} ({ctr_percent_change:.2%} изменение относительно 1 дня назад)"
        bot.sendMessage(chat_id=chat_id, text=msg)
        

    @task
    def week_actions(dau, actions):
        fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(15, 10))
        # Построение графиков для метрик из actions
        for metric_name, ax in zip(actions.columns[1:], axes.flatten()):
            sns.lineplot(data=actions, x=actions.columns[0], y=metric_name, marker='o', ax=ax)
            ax.yaxis.set_major_formatter('{x:,.2f}')
            ax.set_title(metric_name)
            ax.grid(True)
            ax.set_xlabel('')
            ax.set_ylabel('')
        fig.suptitle(f"""Действия в приложении за прошедшую неделю ({start_date.strftime('%d-%m-%Y')} - {end_date.strftime('%d-%m-%Y')})""")
        plt.tight_layout()  
        plot_object = io.BytesIO()
        plt.savefig(plot_object)
        plot_object.seek(0)
        plot_object.name = f"{metric_name}_plot.png"
        plt.close()
        bot.send_photo(chat_id=chat_id, photo=plot_object)

        fig, axes = plt.subplots(2, 1, figsize=(12, 8))

        # График для общего DAU
        sns.lineplot(data=dau, x=dau['date'], y=dau['total_DAU'], marker='o', ax=axes[0])
        axes[0].set_title('Общее DAU за прошедшую неделю')
        axes[0].grid(True)
        axes[0].set_xlabel('')
        axes[0].set_ylabel('')

        # График для DAU в разрезе по платформе
        sns.lineplot(data=dau, x=dau['date'], y=dau['users_ios'], marker='o', label='users_iOS', ax=axes[1])
        sns.lineplot(data=dau, x=dau['date'], y=dau['users_android'], marker='o', label='users_Android', ax=axes[1])
        axes[1].set_title('Общее DAU по платформе за прошедшую неделю')
        axes[1].grid(True)
        axes[1].legend()
        axes[1].set_xlabel('')
        axes[1].set_ylabel('')
        plt.tight_layout()
        plot_object = io.BytesIO()
        plt.savefig(plot_object)
        plot_object.seek(0)
        plot_object.name = f"{metric_name}_plot.png"
        plt.close()
        bot.send_photo(chat_id=chat_id, photo=plot_object)

        

    dau = dau_metrics()
    actions = actions_metrics()
    total_add_metrics(dau, actions)
    week_actions(dau, actions)
    
    
j_lavrenteva_add_report = j_lavrenteva_add_report()

        