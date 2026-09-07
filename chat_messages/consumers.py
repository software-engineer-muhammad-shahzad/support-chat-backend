from channels.generic.websocket import AsyncJsonWebsocketConsumer


class ChatConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        print("WebSocket connection requested")

        await self.accept()

        await self.send_json({
            "type": "connection_established",
            "message": "WebSocket connected successfully!",
        })

    async def disconnect(self, close_code):
        print("WebSocket disconnected:", close_code)

    async def receive_json(self, content, **kwargs):
        print("Received:", content)

        await self.send_json({
            "type": "message",
            "data": content,
        })