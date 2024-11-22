FROM python:latest

RUN pip install kubernetes requests

ADD watcher.py /opt/watcher.py
