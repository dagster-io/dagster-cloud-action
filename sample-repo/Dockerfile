FROM python:3.8-slim

COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

WORKDIR /opt/dagster/app

COPY repo.py /opt/dagster/app