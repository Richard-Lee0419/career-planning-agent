import psycopg2
#测数据库能否成功连接（pgadmin的，暂时可能用不上？）
try:

    conn = psycopg2.connect(
        dbname="My_Project_jobs",
        user="postgres",
        password="314159",
        host="127.0.0.1",
        port="5432",
        options="-c client_encoding=utf8"
    )

    print("数据库连接成功")

    conn.close()

except Exception as e:

    print("数据库连接失败")
    print(e)