FROM python:latest

RUN pip install kubernetes requests pyyaml

ADD . /opt/k8s-watcher
