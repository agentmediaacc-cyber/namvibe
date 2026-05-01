import livestream.routing
import messaging.routing
import core.routing


websocket_urlpatterns = [
    *livestream.routing.websocket_urlpatterns,
    *messaging.routing.websocket_urlpatterns,
    *core.routing.websocket_urlpatterns,
]
