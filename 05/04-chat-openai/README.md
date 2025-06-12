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
