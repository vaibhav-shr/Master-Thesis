FROM ubuntu:16.04
MAINTAINER Vaibhav Sharma

WORKDIR /app

RUN apt-get update
RUN apt-get install -y software-properties-common python-software-properties
RUN apt-get update
RUN apt-get install -y python3.6 && apt-get install -y python3-pip
RUN apt-get install -y python3-dev

ADD requirements.txt /app
ADD run.sh /app
ADD pdffiles /app/pdffiles
RUN pip3 install -r requirements.txt
ADD locust_async.py /app

EXPOSE 5557 5558 8089

RUN chmod 755 run.sh

CMD ./run.sh
