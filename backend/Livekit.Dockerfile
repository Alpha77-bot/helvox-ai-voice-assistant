FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements.txt

RUN pip3 install -r requirements.txt

COPY agent.py .

COPY weaviate_client ./weaviate_client

COPY postgres_client ./postgres_client

RUN python3 agent.py download-files

EXPOSE 8081

CMD ["python3", "agent.py", "dev"]