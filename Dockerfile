from python:3.9-slim

RUN mkdir /opt/arcdiscvist
ADD . /opt/arcdiscvist
WORKDIR /opt/arcdiscvist
RUN apt-get update && apt-get install gpg
RUN pip install -e .

WORKDIR /data
CMD ["sleep", "infinity"]
