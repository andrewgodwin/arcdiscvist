from python:3.9-slim

RUN mkdir /opt/arcdiscvist
ADD . /opt/arcdiscvist
WORKDIR /opt/arcdiscvist
RUN pip install -e .

WORKDIR /data
CMD ["sleep", "infinity"]
