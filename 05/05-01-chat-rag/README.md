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
- chromadb and langchain for RAG implementation
- config.py: SYSTEM_PROMPT centralized as agent system prompt
- chat_api and chat_ui endpoints updated to support RAG context
- chat_ui: initialize_vector_store
- chat_ui: handle_chat_post and handle_chat_get_stream separation


## Design discussion
