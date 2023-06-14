FROM python:3.11.3-slim-buster

WORKDIR /django_ws

COPY requirements.txt .

RUN pip3 install -r requirements.txt

# Install the MySQL client
RUN apt-get update && apt-get install -y default-libmysqlclient-dev

COPY . .

EXPOSE 8000

CMD [ "python", "manage.py", "runserver", "0.0.0.0:8000" ]