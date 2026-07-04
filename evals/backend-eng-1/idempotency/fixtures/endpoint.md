## POST /charge

Creates a payment charge against a customer's card for the given amount. Clients may retry on network timeout, so a duplicate request must not double-charge the customer.
