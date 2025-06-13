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
- chat_ui: streamed chat responses from the agent
- current_app usage
- chat_ui:chat.html added
- chat_api: non-stream and stream endpoints added
- python hooks added for openai_client setup
- chat.http adde