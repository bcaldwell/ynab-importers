FROM ruby:alpine3.7 as ejson
RUN gem install ejson


FROM python:3.7
LABEL author="benjamincaldwell"

RUN pip install pipenv
# && addgroup -S -g 1001 app \
# && adduser -S -D -h /app -u 1001 -G app app
ENV PYTHONUNBUFFERED=0
COPY --from=ejson /usr/local/bundle/gems/ejson-1.2.1/build/linux-amd64/ejson /usr/bin/ejson

# Creating working directory
RUN mkdir -p /app/src
WORKDIR /app/src
# RUN chown -R app.app /app/


COPY Pipfile /app/src/Pipfile
COPY Pipfile.lock /app/src/Pipfile.lock

# set timezone to pst
RUN pipenv install --system
# RUN pipenv lock --requirements > requirements.txt && pip install -r requirements.txt

COPY . /app/src/

# USER app
CMD ["python", "-u", "app.py"]
