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
     'start_date': datetime(2023, 8, 19),
 }

# Интервал запуска DAG 
schedule_interval = '*/15 * * * *'

def check_anomaly(df, metric, a=5, n=5):
    # Функция предлагает алгоритм поиска аномалий в данных (межквартильный размах)
    # вычисляем 25-ый квантиль 
    df['q25'] = df[metric].shift(1).rolling(n).quantile(0.25)
    # вычисляем 75-ый квантиль    
    df['q75'] = df[metric].shift(1).rolling(n).quantile(0.75)
    # межвантильный размах
    df['iqr'] = df['q75'] - df['q25'] 
    # значение верхней границы
    df['up'] = df['q75'] + a*df['iqr'] 
    # значение нижней границы 
    df['low'] = df['q25'] - a*df['iqr']

    df['up'] = df['up'].rolling(window=n, center=True, min_periods = 1).mean()
    df['low'] = df['low'].rolling(window=n, center=True, min_periods = 1).mean()

        
    if df[metric].iloc[-1] < df['low'].iloc[-1] or df[metric].iloc[-1] > df['up'].iloc[-1]:
        is_alert = 1
    else:
        is_alert = 0

    return is_alert, df
    
@dag(default_args=default_args, schedule_interval=schedule_interval, catchup=False)
def j_lavr_alerts_system():
    
    @task       
    def run_alerts():
    # Запрос для метрик из данных по ленте новостей и мессенджера:
        query = """
        SELECT ts, date, hm, likes, views, CTR, users_feed, users_message, sent_messages
        FROM
        (SELECT toStartOfFifteenMinutes(time) AS ts, toDate(time) AS date, 
        formatDateTime(ts, '%R') AS hm,
        COUNT(DISTINCT user_id) AS users_feed, 
        countIf(action='like') AS likes, 
        countIf(action='view') AS views, ROUND(countIf(action='like')/countIf(action='view'), 2) AS CTR
        FROM simulator_20230720.feed_actions
        WHERE time >= today() - 1 AND time < toStartOfFifteenMinutes(now())
        GROUP BY ts, date, hm
        ORDER BY ts) AS t_f
        JOIN
        (SELECT toStartOfFifteenMinutes(time) AS ts, toDate(time) AS date, 
        formatDateTime(ts, '%R') AS hm, 
        COUNT(DISTINCT user_id) AS users_message,
        COUNT(user_id) AS sent_messages
        FROM simulator_20230720.message_actions
        WHERE time >= today() - 1 AND time < toStartOfFifteenMinutes(now())
        GROUP BY ts, date, hm
        ORDER BY ts) AS t_m 
        ON t_f.ts = t_m.ts
        """
        data = ph.read_clickhouse(query, connection=connection)
        #список метрик для данных
        metrics = ['likes', 'views', 'CTR', 'users_feed', 'users_message', 'sent_messages']
        for metric in metrics:
            df = data[['ts', 'date', 'hm', metric]].copy()
            is_alert, df = check_anomaly(df, metric)

            if is_alert == 1:
                msg = '''Сегодня {}\nМетрика {metric}:\nТекущее значение {current_val:.2f}\nОтклонение от предыдущего значения составляет {last_val_diff:.2%}'''\
                                .format(metric=metric, current_val=df[metric].iloc[-1],\
                                last_val_diff=abs(1-df[metric].iloc[-1]/df[metric].iloc[-2]))
                # формируем текстовый шаблон нашего алерта и отправляем в телеграмм
                bot.sendMessage(chat_id=chat_id, text=msg)
                #строим и отправляем графики
                sns.set(rc={'figure.figsize': (16, 10)})
                plt.tight_layout()
                ax = sns.lineplot(x=df['ts'], y=df[metric], label=metric)
                ax = sns.lineplot(x=df['ts'], y=df['up'], label='up')
                ax = sns.lineplot(x=df['ts'], y=df['low'], label='low')

                for ind, label in enumerate(ax.get_xticklabels()):
                    if ind % 2 == 0:
                        label.set_visible(True)
                    else:
                        label.set_visible(False)

                ax.set_title(metric)
                ax.set(ylim=(0, None))
                plot_object = io.BytesIO()
                plt.savefig(plot_object)
                plot_object.name = '{0}.png'.format(metric)
                plot_object.seek(0)
                plt.close()
                bot.sendPhoto(chat_id=chat_id, photo=plot_object)
                    
    run_alerts()
    
j_lavr_alerts_system = j_lavr_alerts_system()