Run the app using 

For development mode

```bash
python -m quart --app src.myapp run --port 50505 --reload
```


For production mode

```bash
gunicorn --config gunicorn.conf.py "myapp:create_app()"
```

## Changes
- server side storage implemented (in-memory)
- chat.html: call to POST /conversations to get a new conversation_id
- chat.html: The AIChatProtocolClient sends the conversation_id to /chat/stream
- chat_ui: Handles the conversation_id to retrieve the conversation history and send it to openai_client
- storage: ConversationStorage Abstract class defined 
- storage: InMemoryConversationStorage added

## Design discussion
- in-memory server side storage
- complexity added
- AIChatProtocolClient has no updates since 2024