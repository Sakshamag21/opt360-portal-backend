import subprocess
import sys
import os
import importlib
package = "reportlab"
try:
    importlib.import_module(package)
except ImportError:
    subprocess.check_call([
        sys.executable, "-m", "pip", "install",
        '--no-cache-dir',
        '--index-url', 'http://10.10.206.59:8080/repository/pypi-proxy/simple',
        '--trusted-host', '10.10.206.59',
        package
    ])
    # Now force-import without relying on reload(site)
    import importlib
    importlib.invalidate_caches()
    globals()[package] = importlib.import_module(package)

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime
import time
from airflow.utils.dates import days_ago
from kafka import KafkaProducer, KafkaConsumer
from dataclasses import dataclass, field
from typing import List, Optional
import uuid
import json
import logging
import pandas as pd
from trino.dbapi import connect
import mysql.connector
from io import BytesIO
import requests
import base64
from reportlab.lib.pagesizes import letter, landscape, A3, A2, A1, A4,A5
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

connection_url="10.10.108.224"
admin_user="Data_platform_W"
admin_password="Dataplat_7634"

trino_host="10.10.116.75"
trino_catalog_iceberg='strot'
trino_port=8080
trino_user="opt360"

topic = 'COMMAND.STROT.RCS.REQUEST'

rcs_host = '10.81.116.128'
rcs_port = '9090'

mail_list=["techexe16.yp25@uidai.net.in"]
cc="sakshamag277@gmail.com"

logging.basicConfig(
    level=logging.DEBUG,  
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='opt360_checking.log',   
    filemode='w'          
)

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 5, 7),
    'email': ['techexecutive16-yp25@uidai.net.in'],
    'email_on_failure': True,
    'email_on_retry': True,
    'retries': 1,
    
}

dag = DAG(
    'operator360_health_report',
    default_args=default_args,
    description='DAG to check the operator360 enviroment and generate the health check report',
    schedule="0 6 * * *",
    catchup=False,
    concurrency=1,
    tags=['Operator360','health_check']
)

def trino(query, host=trino_host, port=trino_port, user=trino_user):
    try:
        start_time= time.time()
        conn = connect(
            host=host,
            port=port,
            user=user
        )
        cur = conn.cursor()
        cur.execute(query)
        body = cur.fetchall()
        end_time= time.time()
        if not body:
            return {"query": query, "success": 1, "data": body, "execution_time": end_time-start_time}
        else:
            cols = [i[0] for i in cur.description]
            df = pd.DataFrame(body, columns=cols)
            return {"query": query, "success": 1, "data": (cols, body), "df": df, "execution_time": end_time-start_time}
    except Exception as e:
        return {"query": query, "success": 0, "msg": str(e)}

def execute_query(query,host,admin_user=admin_user,admin_password=admin_password):
    connection = mysql.connector.connect(
        host=host,
        user=admin_user,
        password=admin_password
    )
    cursor = connection.cursor()
    cursor.execute(query)
    results=cursor.fetchall()
    connection.close()
    return results

def generate_robust_pdf_to_base64(dfs_dict, paper_size="A5", max_cols_per_table=12, save_path=None):
    """
    Generates a PDF report as a Base64 string.
    Optionally saves to save_path if provided.
    """
    # 1. Use BytesIO to keep the PDF in memory
    pdf_buffer = BytesIO()
    
    # 2. Set Paper Size
    if paper_size.upper() == "A5":
        page_layout = landscape(A5)
    else:
        page_layout = landscape(letter)
        
    # Build doc using the buffer instead of a filename
    doc = SimpleDocTemplate(pdf_buffer, pagesize=page_layout, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=20)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    title_style.textColor = colors.HexColor("#333333")
    
    subtitle_style = styles['Normal']
    subtitle_style.textColor = colors.HexColor("#666666")

    for title, df in dfs_dict.items():
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 10))
        
        total_cols = len(df.columns)
        
        for i in range(0, total_cols, max_cols_per_table):
            chunk_df = df.iloc[:, i:i+max_cols_per_table]
            
            if total_cols > max_cols_per_table:
                col_start = i + 1
                col_end = min(i + max_cols_per_table, total_cols)
                story.append(Paragraph(f"<i>Part {i//max_cols_per_table + 1} (Columns {col_start} to {col_end})</i>", subtitle_style))
                story.append(Spacer(1, 5))
            
            data = [chunk_df.columns.to_list()] + chunk_df.fillna("").astype(str).values.tolist()
            
            table = Table(data, repeatRows=1)
            style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4F81BD")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8), 
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ])
            
            for row_idx in range(1, len(data)):
                bg_color = colors.HexColor("#F0F4FA") if row_idx % 2 == 0 else colors.white
                style.add('BACKGROUND', (0, row_idx), (-1, row_idx), bg_color)
                
            table.setStyle(style)
            story.append(table)
            story.append(Spacer(1, 15))
            
        story.append(Spacer(1, 20))

    # 3. Finalize the PDF construction
    doc.build(story)

    # 4. Handle Saving (Optional)
    pdf_value = pdf_buffer.getvalue()
    if save_path:
        with open(save_path, "wb") as f:
            f.write(pdf_value)
        print(f"File saved locally at: {save_path}")

    # 5. Encode to Base64
    encoded_pdf = base64.b64encode(pdf_value).decode('utf-8')
    pdf_buffer.close()
    
    return encoded_pdf


def send_email_team(email, additional_info):
    url = f'http://{rcs_host}:{rcs_port}/messageReceiver/v1'
    
    payload = json.dumps({

    "residentId": "720447260190",
    "appName": "STROT",
    "idType": "uid",
    "event": "STROT_REPORT",
    "mobile": "8540864693",
    "email": email,
    "channel": [
        {
            "language": "23",
            "channel": "EMAIL"
        }

    ],
    "additionalInfo": additional_info
    })

    headers = {'content-type': 'application/json', 'Accept-Charset': 'UTF-8'}
    response = requests.post(url, data=payload, headers=headers)
    return response,email



def get_checking_matrix():
    feature_count_df=trino('''
        select status, count(*) as status_count from strot.operator360.opt360_features group by 1 
    ''',host='10.10.116.75')

    if 'df' not in feature_count_df:
        print(feature_count_df)
        feature_count_df['df']= pd.DataFrame()

    feature_instances_count_df=pd.DataFrame({'feature_id':[], 'destination_table':[], 'count':[], 'last_updated_date':[]})

    features_df= trino('''
        select feature_name, version,feature_id, destination_table from strot.operator360.opt360_features 
        where status='PROD' order by feature_id
    ''',host='10.10.116.75')

    if 'df' in features_df:
        for i,r in features_df['df'].iterrows():
            feat_id= r['feature_id']
            dest_tab= r['destination_table']
            # print(feat_id, dest_tab)
            count_id= trino(f'''
                select count(*) as coun from {dest_tab} where feature_id='{feat_id}' and date(timestamp)= date(current_date - interval '1' day)
            ''',host='10.10.116.75',user='saksham')
            
            # print(count_id['df']['coun'].to_list()[0])
            if  'df' in count_id and count_id['df']['coun'].to_list()[0] == 0:
                last_date= trino(f'''
                    select max(date(timestamp)) as last_updated_date from {dest_tab} where feature_id='{feat_id}'
                ''',host='10.10.116.75',user='saksham')
                # print(last_date['df']['last_updated_date'].to_list()[0])
                if 'df' in last_date:
                    last_updated_date=last_date['df']['last_updated_date'].to_list()[0]
                else:
                    last_updated_date="error"

            else:
                last_updated_date=datetime.now().strftime("%Y-%m-%d")
                
            # print(count_id) 
            feature_instances_count_df.loc[len(feature_instances_count_df)] =[feat_id, dest_tab, count_id['df']['coun'].to_list()[0] if 'df' in count_id else 0,last_updated_date]
            # print("length:",len(feature_instances_count_df))
    
    signals_count_df= trino('''
        select signal_name ,count(*) 
        from flink_stream.operator360.signals_audit_v1 
        where date(created_at)= date(current_date - interval '1' day)
        group by 1
    ''',host='10.10.116.75')

    if 'df' not in signals_count_df:
        print(signals_count_df)
        signals_count_df['df']=pd.DataFrame()

    suspension_signal_count_df= trino('''
        select disposition_code ,count(*) 
        from strot.operator360.suspension_signals 
        where date(event_timestamp)= date(current_date - interval '1' day)
        group by 1
    ''',host='10.10.116.75')

    if 'df' not in suspension_signal_count_df:
        print(suspension_signal_count_df)
        suspension_signal_count_df['df']=pd.DataFrame()

    suspension_signals_df= trino('''
        select entity_id , disposition_code
        from strot.operator360.suspension_signals 
        where date(event_timestamp)= date(current_date - interval '1' day)
    ''',host='10.10.116.75')

    if 'df' not in suspension_signals_df:
        print(suspension_signals_df)
        suspension_signals_df['df']=pd.DataFrame()

    
    opt_master_df= pd.DataFrame({'date':[],'count':[]})
    query="select count(*), date(updated_at) from operator360.opt_master group by 2"
    opt_master_update=execute_query(query, connection_url)

    for dt in opt_master_update:
        print(dt)
        opt_master_df.loc[len(opt_master_df)]=[dt[1],dt[0]]

    last_updated_features_df=trino('''
        select feature_id, destination_table, date(created_at) as created_at, created_by, date(updated_at) as updated_at, updated_by from strot.operator360.opt360_features where date(created_at)= date(current_date - interval '1' day) or date(updated_at)= date(current_date - interval '1' day)
    ''',host='10.10.116.75')

    if 'df' not in last_updated_features_df:
        print(last_updated_features_df)
        last_updated_features_df['df']=pd.DataFrame()

    
    return {
        "Feature Count Overview": feature_count_df['df'],
        "Feature Instances Count": feature_instances_count_df,
        "Signals Count": signals_count_df['df'],
        "Suspension Signal Count": suspension_signal_count_df['df'],
        "Suspension Signals ": suspension_signals_df['df'],
        "Last Updated Features": last_updated_features_df['df'],
        "Opt_master MYSQL Table Update":opt_master_df
    }


def trigger_email(query, email_list):
    today_date1 = datetime.now().strftime("%d_%B_%Y")
    today_date = datetime.now().strftime("%d %B %Y")
    file_name = f"Operator360_System_Check_Report.pdf"
    my_report_data = get_checking_matrix()

    html_content1 = f"<p>Please find the attached Operator360 system check report for: {today_date1}.</p>"
    # encoded_csv = query_to_base64(query)
    pdf_base64 = generate_robust_pdf_to_base64(
        my_report_data, 
        paper_size="A5", 
        save_path="Operator360_System_Check_Report.pdf" 
    )
    html_content = html_content1 
    emailSubject= f"Operator 360 System Check Report for {today_date}"
    additional_info = {
            "HTML_CONTENT": html_content,
            "TITLE":" ",
            "RECEIVER": "Team",
            "emailSubject": emailSubject,
            "cc": cc,
        }

    if pdf_base64 and isinstance(pdf_base64, str) and pdf_base64 != "1":
        additional_info["attachment"] = pdf_base64
        additional_info["fileName"] = file_name

    if pdf_base64 != 0:
        for email in email_list:
            response, email = send_email_team(email, additional_info)
            if(response.status_code==200):
                print(f"Email sent to {email}: {response.status_code}, {response}")
            else:
                print(email,response.status_code)
    else:
        print("Query failed — Trino query did not return data or failed to execute.")
        raise RuntimeError("Trino query failed — encoded_csv is 0. DAG will now fail to trigger alert.")
 
opt360_checking_report_task=  PythonOperator(
                task_id='opt360_checking_report',
                python_callable=trigger_email,
                op_kwargs={'query':'','email_list':mail_list},
                trigger_rule='all_done',
                dag=dag,
            )

opt360_checking_report_task


    


