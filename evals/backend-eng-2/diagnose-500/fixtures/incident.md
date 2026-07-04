## Incident: order-service 500s on `/orders/:id/charge`

Stack trace from the error tracker:

```
Traceback (most recent call last):
  File "order_service.py", line 42, in charge_customer
    amount = order.total_amount
AttributeError: 'NoneType' object has no attribute 'total_amount'
```

Frequency: spikes correlate with the `/orders/:id/charge` endpoint receiving
requests for `order_id` values belonging to orders that were deleted moments
earlier by a nightly cleanup job. `order` is fetched with `Order.get(order_id)`,
which returns `None` when the row no longer exists, and the code proceeds to
read `order.total_amount` without checking for `None` first.
