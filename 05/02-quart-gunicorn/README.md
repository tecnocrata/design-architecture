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

- app as module (__init__.py file added)
- same endpoints logic preserved but Quart app is passed to module init
- flit as build system added (pyproject.toml)
- gunicorn and uvicorn added
- gunicorn.conf.py file added with workers definition
- run in dev mode
- run it in prod mode