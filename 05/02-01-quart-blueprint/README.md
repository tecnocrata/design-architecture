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

- app.py splitted into two api and ui files
- blueprint used for concern separation
- template needs to refer to the module (chat_ui)