from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import uuid
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Message:
    role: str
    content: str
    timestamp: datetime = datetime.utcnow()

@dataclass
class Conversation:
    id: str
    messages: List[Message]
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()

class ConversationStorage(ABC):
    @abstractmethod
    async def create_conversation(self) -> str:
        """Create a new conversation and return its ID."""
        pass

    @abstractmethod
    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        pass

    @abstractmethod
    async def add_message(self, conversation_id: str, role: str, content: str) -> None:
        """Add a message to a conversation."""
        pass

    @abstractmethod
    async def get_messages(self, conversation_id: str) -> List[Dict]:
        """Get all messages from a conversation in the format expected by OpenAI."""
        pass

class InMemoryConversationStorage(ConversationStorage):
    def __init__(self):
        self._conversations: Dict[str, Conversation] = {}

    async def create_conversation(self) -> str:
        conversation_id = str(uuid.uuid4())
        self._conversations[conversation_id] = Conversation(
            id=conversation_id,
            messages=[]
        )
        return conversation_id

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        return self._conversations.get(conversation_id)

    async def add_message(self, conversation_id: str, role: str, content: str) -> None:
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        message = Message(role=role, content=content)
        conversation.messages.append(message)
        conversation.updated_at = datetime.utcnow()

    async def get_messages(self, conversation_id: str) -> List[Dict]:
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        return [{"role": msg.role, "content": msg.content} for msg in conversation.messages] 