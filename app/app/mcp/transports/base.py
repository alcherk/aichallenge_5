from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class MCPTransport(ABC):
    @abstractmethod
    async def request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Perform a JSON-RPC request and return the raw JSON response object.
        """

    @abstractmethod
    async def notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """
        Send a JSON-RPC notification (no response expected).
        """

    @abstractmethod
    async def aclose(self) -> None:
        """
        Close transport resources.
        """


