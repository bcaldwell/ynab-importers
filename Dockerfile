FROM ruby:alpine3.7 as ejson
RUN gem install ejson


FROM python:3.7-alpine
MAINTAINER benjamincaldwell

RUN apk update \
    && apk add --no-cache git openssh-client \
    && pip install pipenv \
    && addgroup -S -g 1001 app \
    && adduser -S -D -h /app -u 1001 -G app app

COPY --from=ejson /usr/local/bundle/gems/ejson-1.2.1/build/linux-amd64/ejson /usr/bin/ejson

# Creating working directory
RUN mkdir /app/src
WORKDIR /app/src
RUN chown -R app.app /app/

USER app

COPY Pipfile /app/src/Pipfile
# COPY Pipfile.lock /app/src/Pipfile.lock

RUN pipenv install

COPY . /app/src/

CMD ["python", "app.py"]