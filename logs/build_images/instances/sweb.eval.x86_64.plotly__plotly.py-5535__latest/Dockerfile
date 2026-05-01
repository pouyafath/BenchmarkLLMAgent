FROM --platform=linux/x86_64 sweb.env.py.x86_64.f8897316f59ee2624f22a3:latest

COPY ./setup_repo.sh /root/
RUN sed -i -e 's/\r$//' /root/setup_repo.sh
RUN /bin/bash /root/setup_repo.sh

WORKDIR /testbed/
