FROM python:3.8.3

RUN apt -y update
RUN apt install -y python-pip python-dev build-essential
RUN pip install --upgrade pip
ADD requirements.txt .
RUN pip install -U -r requirements.txt

WORKDIR /app
