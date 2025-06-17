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
- chat bot to agent transition
- config.py: Prompt changed to agentic styled prompt. The 'movie_database_search' is being referenced.
- init.py: agent_executor and vector_store_retriever definitions
- tools.py: tools definition placeholder
- tools.py: get_movie_retriever_tool returns the 'movie_database_search' tool
- tools.py: movie_database_search retrieves documents from the vectore store
- vectore_store_manager: defines the initialize_vector_store method

## Design discussion
- agent_executor
- extensible tooling feature.
- non complex agents