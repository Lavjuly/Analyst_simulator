from datetime import datetime, timedelta
import pandas as pd
import pandahouse as ph
from airflow.decorators import dag, task
from airflow.operators.python import get_current_context

connection = {'host': 'https://clickhouse.lab.karpov.courses',
                      'database':'simulator_20230720',
                      'user':'student', 
                      'password':'dpo_python_2020'}

connection_test = {'host': 'https://clickhouse.lab.karpov.courses',
                      'database':'test',
                      'user':'student-rw', 
                      'password':'656e2b0c9c'}


# Дефолтные параметры, которые прокидываются в таски
default_args = {
    'owner': 'j-lavrenteva',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2023, 8, 13),
}

# Интервал запуска DAG (ежедневно в 10:00)
schedule_interval = '0 10 * * *'

@dag(default_args=default_args, schedule_interval=schedule_interval, catchup=False)
def j_lavrenteva_dag_ETL():
    
    @task()
    def extract_feed_actions():
        feed_actions_query = """
        SELECT user_id, countIf(action='view') AS views,
        countIf(action='like') AS likes, gender, age, os, toDate(time) as event_date
        FROM simulator_20230720.feed_actions
        WHERE toDate(time) = toDate(today()) - 1
        GROUP BY user_id, gender, age, os, toDate(time)
        """
        
        feed_data = ph.read_clickhouse(feed_actions_query, connection=connection)
        return feed_data
    
    
    @task()
    def extract_message():
        message_query = """
        SELECT user_id, 
        messages_received, messages_sent, users_received, users_sent
        FROM 
        (SELECT user_id, 
        COUNT(reciever_id) AS messages_sent, 
        COUNT(distinct reciever_id) AS users_sent
        FROM simulator_20230720.message_actions
        WHERE toDate(time) = toDate(now()) - 1
        GROUP BY user_id) AS senders
        JOIN 
        (SELECT reciever_id, 
        COUNT(user_id) AS messages_received, 
        COUNT(distinct user_id) AS users_received
        FROM simulator_20230720.message_actions
        WHERE toDate(time) = toDate(now()) - 1
        GROUP BY reciever_id) AS recievers
        ON senders.user_id = recievers.reciever_id
        """
        
        message_data = ph.read_clickhouse(message_query, connection=connection)
        return message_data
    
    #объединяем результаты двух таблиц
    @task()
    def transform_joined_df(feed_data, message_data):
        df_joined = pd.merge(feed_data, message_data, on='user_id', how='left').copy()
        return df_joined
    
    #создаем срез по полу
    @task()
    def transform_df_gender(df_joined):
        df_gender = df_joined.groupby(['gender', 'event_date'])['likes', 'views', 'messages_received', 'messages_sent', 'users_received', 'users_sent'].sum().reset_index()
        df_gender.rename(columns = {'gender' : 'dimension_value'}, inplace = True)
        df_gender.insert(0, 'dimension', 'gender')
        return df_gender
    
    #создаем срез по операционной системе
    @task()
    def transform_df_os(df_joined):
        df_os = df_joined.groupby(['os', 'event_date'])['likes', 'views', 'messages_received', 'messages_sent', 'users_received', 'users_sent'].sum().reset_index()
        df_os.rename(columns = {'os' : 'dimension_value'}, inplace = True)
        df_os.insert(0, 'dimension', 'os')
        return df_os
    
    #создаем срез по возрасту пользователей
    @task()
    def transform_df_age(df_joined):
        new_df_age = df_joined.drop(columns=['age']).copy() 
        new_df_age['age_group'] = pd.cut(df_joined['age'], bins = [0, 17 , 25, 35, 45, 100], labels =['0-17', '18-25', '26-35', '36-45', '45+'])
        df_age = new_df_age.groupby(['age_group', 'event_date'])['likes', 'views', 'messages_received', 'messages_sent', 'users_received', 'users_sent'].sum().reset_index() 
        df_age.rename(columns = {'age_group' : 'dimension_value'}, inplace = True)
        df_age.insert(0, 'dimension', 'age')
        return df_age
    
    #объединяем все срезы в одну таблицу
    @task() 
    def transform_df_contact(df_gender, df_os, df_age):
        df_load = pd.concat([df_gender, df_os, df_age]).reset_index(drop=True)
        df_load['messages_received'] = df_load['messages_received'].astype('int')
        df_load['messages_sent'] = df_load['messages_sent'].astype('int')
        df_load['users_received'] = df_load['users_received'].astype('int')
        df_load['users_sent'] = df_load['users_sent'].astype('int')
        return df_load
    
    #выгружаем результат в новую таблицу 
    @task
    def load(df_load):
        create_table_query = """
        CREATE TABLE IF NOT EXISTS test.j_lavrenteva
        (
        dimension String,
        dimension_value String,
        event_date Date,
        likes UInt64,
        views UInt64,
        messages_received UInt64,
        messages_sent UInt64,
        users_received UInt64,
        users_sent UInt64
        )
        ENGINE = MergeTree()
        ORDER BY event_date
        """
        ph.execute(create_table_query, connection=connection_test)
        ph.to_clickhouse(df_load, 'j_lavrenteva', index=False, connection=connection_test)
        
        
    feed_data = extract_feed_actions()
    message_data = extract_message()
    df_joined = transform_joined_df(feed_data, message_data)
    df_gender = transform_df_gender(df_joined)
    df_os = transform_df_os(df_joined)
    df_age = transform_df_age(df_joined)
    df_load = transform_df_contact(df_gender, df_os, df_age)
    load(df_load) 

j_lavrenteva_dag_ETL = j_lavrenteva_dag_ETL()





        

        
