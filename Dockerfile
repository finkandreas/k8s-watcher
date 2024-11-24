FROM python:latest

RUN pip install kubernetes requests

ADD . /opt/k8s-watcher
