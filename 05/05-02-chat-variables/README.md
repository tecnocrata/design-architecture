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
- config.py: prompt_template instead of string prompt
- chat_ui: prompt_template used
- chat_ui: vectore store added as context explicitly
- chat_api: similar change added


## Design discussion
- what if more task are required?
- the vectore store call is being hard coded before the llm invocation.