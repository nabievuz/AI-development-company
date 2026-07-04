def get_user(name):
    conn = db.connect()
    sql = f"SELECT * FROM users WHERE name = '{name}'"
    return conn.execute(sql)
