# Импортируем необходимые библиотеки
import telegram
import matplotlib.pyplot as plt
import seaborn as sns
import io
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

my_token = '6594134478:AAEkclw9_TgX4nkqjBVp3QafS_KzK1JouP8' # токен моего бота
bot = telegram.Bot(token=my_token) # получаем доступ
chat_id = -927780322

# Дефолтные параметры, которые прокидываются в таски
default_args = {
    'owner': 'j-lavrenteva',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2023, 8, 14),
}

# Интервал запуска DAG (ежедневно в 11:00)
schedule_interval = '0 11 * * *'

# Делаем запрос по ключевым метрикам за вчера
yd_query = """
        SELECT toDate(time) AS date, COUNT(DISTINCT user_id) AS DAU, countIf(action = 'like') AS likes, 
        countIf(action = 'view') AS views, ROUND(countIf(action = 'like')/countIf(action = 'view'), 2) AS CTR
        FROM simulator_20230720.feed_actions
        WHERE toDate(time) = toDate(now()) - 1
        GROUP BY date
        """

# Делаем запрос по ключевым метрикам за предыдущие 7 дней
week_query = """
        SELECT toDate(time) AS date, COUNT(DISTINCT user_id) AS DAU, countIf(action = 'like') AS likes, 
        countIf(action = 'view') AS views, countIf(action = 'like')/countIf(action = 'view') AS CTR
        FROM simulator_20230720.feed_actions
        WHERE toDate(time) BETWEEN toDate(now()) - 7 AND toDate(now()) - 1
        GROUP BY date
        """

@dag(default_args=default_args, schedule_interval=schedule_interval, catchup=False)
def j_lavrenteva_bot_report():
    
    @task()
    def metrics_report():
        # Отчет по ключевым метрикам за вчера
        yd_metrics = ph.read_clickhouse(yd_query, connection=connection)
        yd_date = date.today() - timedelta(days=1)
        msg = f"Metrics for {yd_date.strftime('%d-%m-%Y')}:\n\n" \
               f"DAU = {yd_metrics.loc[0, 'DAU']}\n" \
               f"likes = {yd_metrics.loc[0, 'likes']}\n" \
               f"views = {yd_metrics.loc[0, 'views']}\n" \
               f"CTR = {yd_metrics.loc[0, 'CTR']}"
        bot.sendMessage(chat_id=chat_id, text=msg)
       
        
    @task()
    def plot_and_send_metrics():
        # Отчет по ключевым метрикам за 7 дней
        week_metrics = ph.read_clickhouse(week_query, connection=connection)
        start_date = date.today() - timedelta(days=7)
        end_date = date.today() - timedelta(days=1)
        fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(15, 10))
        for metric_name, ax in zip(week_metrics.columns[1:], axes.flatten()):
            sns.lineplot(data=week_metrics, x=week_metrics.columns[0], y=metric_name, ax=ax)
            ax.set_title(metric_name)
            ax.set_xlabel('')
            ax.set_ylabel('')
        fig.suptitle(f"""Key metrics for the last week ({start_date.strftime('%d-%m-%Y')} - {end_date.strftime('%d-%m-%Y')})""")
        plt.tight_layout()  # автоматическое расположение графиков для лучшей читаемости
        plot_object = io.BytesIO()
        plt.savefig(plot_object)
        plot_object.seek(0)
        plot_object.name = f"{metric_name}_plot.png"
        plt.close()
        bot.send_photo(chat_id=chat_id, photo=plot_object)

    yd_metrics = metrics_report()
    week_metrics = plot_and_send_metrics()

j_lavrenteva_bot_report = j_lavrenteva_bot_report()
