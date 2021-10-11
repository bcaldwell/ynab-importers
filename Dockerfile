FROM alpine as ejson
ARG TARGETPLATFORM
RUN wget -O /ejson "https://github.com/Shopify/ejson/releases/download/v1.3.0/${TARGETPLATFORM/\//-}" \
    && chmod +x /ejson


FROM python:3.9
LABEL author="benjamincaldwell"

RUN  (rm /usr/bin/lsb_release || echo 0) && pip install pipenv
# && addgroup -S -g 1001 app \
# && adduser -S -D -h /app -u 1001 -G app app
ENV PYTHONUNBUFFERED=0
COPY --from=ejson /ejson /usr/bin/ejson

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
