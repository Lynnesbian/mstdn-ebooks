FROM golang:1.11.1-alpine

COPY . /mstdn-ebooks/
RUN cd /mstdn-ebooks/ \
 && apk add --no-cache git \
 && CGO_ENABLED=0 go build -o /usr/local/bin/mstdn-ebooks \
 && apk del git

VOLUME /mstdn-ebooks/data
WORKDIR /mstdn-ebooks/data

CMD ["mstdn-ebooks", "-server", "https://botsin.space"]
