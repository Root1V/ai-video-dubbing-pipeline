"""Dashboard web de administracion (Prosodia Web): API REST + tareas Celery + persistencia.

Este subpaquete envuelve el pipeline existente (`video_translator`) como un
segundo "driver" (junto a `cli.py`), sin modificar `application`/`domain`.
"""
