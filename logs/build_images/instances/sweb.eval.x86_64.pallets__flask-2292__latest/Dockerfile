FROM --platform=linux/x86_64 sweb.env.py.x86_64.4df0bef74dbb052e7f8fe2:latest

COPY ./setup_repo.sh /root/
RUN sed -i -e 's/\r$//' /root/setup_repo.sh
RUN /bin/bash /root/setup_repo.sh

WORKDIR /testbed/
