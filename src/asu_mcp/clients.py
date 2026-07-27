"""One instance of each source client, shared by every tool.

Each client owns an HTTP connection pool and its own TTL cache, so a second
instance would double the traffic ASU sees for identical questions. That
matters most for search_asu, which deliberately asks the same questions the
individual tools do -- sharing these means a follow-up search_classes after a
search_asu is a cache hit rather than another request.
"""

from __future__ import annotations

from .classes.client import ClassSearchClient
from .events.client import EventsClient
from .news.client import NewsClient
from .people.client import PeopleClient

classes = ClassSearchClient()
events = EventsClient()
news = NewsClient()
people = PeopleClient()
