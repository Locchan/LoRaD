FROM python:3-alpine

RUN mkdir /tmp/lorad
WORKDIR /tmp/lorad

COPY . .
RUN apk add ffmpeg && pip install poetry
RUN poetry build
RUN pip install dist/*.whl
RUN cp /tmp/lorad/lorad_main.py /usr/bin/lorad && cp -rf /tmp/lorad/resources /resources
RUN rm -rf /tmp/lorad

RUN ln -s /usr/share/zoneinfo/Europe/Minsk /etc/localtime

WORKDIR /
EXPOSE 5475
ENTRYPOINT [ "lorad" ]