FROM python:3.7

RUN apt -y update
RUN apt install -y python-pip python-dev build-essential
RUN pip install pandas numpy tensorflow==1.15.4

WORKDIR /app
