from __future__ import annotations

import os
import time
from typing import Optional

import jwt


class LiveKitService:
    def __init__(self) -> None:
        self.ws_url = os.getenv("ACE_LIVEKIT_WS_URL", "ws://127.0.0.1:7880")
        self.api_key = os.getenv("ACE_LIVEKIT_API_KEY", "devkey")
        self.api_secret = os.getenv("ACE_LIVEKIT_API_SECRET", "devsecretkey_for_local_livekit_32chars")

    def manager_token(self, *, room_name: str, identity: str, display_name: str) -> str:
        return self._build_token(
            room_name=room_name,
            identity=identity,
            display_name=display_name,
            can_publish=True,
            can_subscribe=False,
        )

    def visitor_token(self, *, room_name: str, identity: str, display_name: str) -> str:
        return self._build_token(
            room_name=room_name,
            identity=identity,
            display_name=display_name,
            can_publish=False,
            can_subscribe=True,
        )

    def _build_token(
        self,
        *,
        room_name: str,
        identity: str,
        display_name: str,
        can_publish: bool,
        can_subscribe: bool,
    ) -> str:
        now = int(time.time())
        payload = {
            "iss": self.api_key,
            "sub": identity,
            "nbf": now - 5,
            "exp": now + 60 * 60,
            "name": display_name,
            "video": {
                "roomJoin": True,
                "room": room_name,
                "canPublish": can_publish,
                "canSubscribe": can_subscribe,
                "canPublishData": can_publish,
            },
        }
        return jwt.encode(payload, self.api_secret, algorithm="HS256")


service = LiveKitService()
