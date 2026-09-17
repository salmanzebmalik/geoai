from threading import local

import requests


_thread_state = local()


def get_http_session() -> requests.Session:
    """
    Return one reusable Requests session per backend worker thread.

    FastAPI executes synchronous endpoints in a thread pool. A thread-local
    session provides connection reuse without sharing one Session object
    concurrently between different threads.
    """

    session = getattr(_thread_state, "session", None)

    if session is None:
        session = requests.Session()
        session.trust_env = False
        _thread_state.session = session

    return session