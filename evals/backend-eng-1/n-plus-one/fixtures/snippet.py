def load_orders(users):
    result = []
    for u in users:
        orders = db.query(Order).filter(user_id=u.id)
        result.append(orders)
    return result
