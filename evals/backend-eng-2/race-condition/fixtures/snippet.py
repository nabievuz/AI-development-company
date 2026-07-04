def reserve_seat(seat_id, user_id, db):
    seat = db.get(Seat, seat_id)
    if seat.status == "available":
        seat.status = "reserved"
        seat.user_id = user_id
        db.save(seat)
    return seat
