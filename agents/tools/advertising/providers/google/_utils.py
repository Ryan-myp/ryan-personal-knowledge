"""Small helpers for account-scoped Google handlers."""


def for_customer(client, customer_id):
    """Use an isolated customer view when the client supports it.

    Looking up the method on the class avoids accidentally treating a fake
    client's permissive ``__getattr__`` as a real scoping implementation.
    """
    method = getattr(type(client), "for_customer", None)
    if method is not None:
        return method(client, customer_id)
    if customer_id and hasattr(client, "customer_id"):
        client.customer_id = customer_id
    return client
