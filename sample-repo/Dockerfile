FROM python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f

COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

WORKDIR /opt/dagster/app

COPY repo.py /opt/dagster/app
