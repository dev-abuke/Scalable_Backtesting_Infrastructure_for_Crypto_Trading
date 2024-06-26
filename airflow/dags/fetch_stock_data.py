from airflow import DAG
from airflow.operators.python_operator import PythonOperator

from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import os

# from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

DATABASE_URL = os.getenv("PYCOPG_DATABASE_URL", "postgresql+psycopg2://trading_db_av2v_user:210M6MA9QKEEgVdiasnUdMQDBNN417oy@dpg-cpqojbqj1k6c73bkqq3g-a.oregon-postgres.render.com/trading_db_av2v")    
engine = create_engine(DATABASE_URL)
# Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# db = Session()

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 6, 20),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Create a DAG
dag = DAG(
    'fetch_stock_data_and_monitoring',
    default_args=default_args,
    description='Fetch stock data daily, store in PostgreSQL, and monitor data quality',
    schedule_interval=timedelta(days=1),
)

def check_data_quality():
    data = pd.read_sql('SELECT * FROM stock_data', con=engine)
    if data.isnull().values.any():
        raise ValueError("Data quality check failed: Found missing values")
    print("Data quality check passed")
    
def fetch_and_store_stock_data():
    # Fetch stocks from database
    stocks_df = pd.read_sql("SELECT * FROM stocks", engine)

    # Fetch data from yfinance
    for index, row in stocks_df.iterrows():
        ticker = row['symbol']
        try:
            print(f"Fetching data for {ticker}")
            data: pd.DataFrame = yf.download(ticker, start='2023-01-01', end=datetime.today().strftime('%Y-%m-%d'))
            if not data.empty:
                data['symbol'] = ticker
                data.reset_index(inplace=True)
                data.rename(columns={
                    'Date': 'date', 
                    'Open': 'open', 
                    'High': 'high', 
                    'Low': 'low', 
                    'Close': 'close', 
                    'Adj Close': 'adj_close', 
                    'Volume': 'volume'
                }, inplace=True)
                # Ensure we don't overwrite by specifying the index as False
                data.to_sql('stock_data', engine, if_exists='append', index=False)
                print(f"Successfully stored data for {ticker}")
            else:
                print(f"No data found for {ticker}")
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")

fetch_data_task = PythonOperator(
    task_id='fetch_and_store_stock_data',
    python_callable=fetch_and_store_stock_data,
    dag=dag,
)

quality_check_task = PythonOperator(
    task_id='check_data_quality',
    python_callable=check_data_quality,
    dag=dag,
)

fetch_data_task >> quality_check_task
